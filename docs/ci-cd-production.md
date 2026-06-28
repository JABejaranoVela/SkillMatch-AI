# CI/CD de produccion

Esta es la guia principal del CI/CD de produccion de SkillMatch AI. Documenta el
workflow real, la preparacion del VPS, las comprobaciones posteriores y los
problemas encontrados durante su puesta en marcha.

No contiene secretos, claves privadas, tokens ni el contenido de `.env.prod`.

## 1. Estado y alcance

El despliegue automatico esta operativo sobre:

- GitHub Actions para validacion, build y despliegue.
- GitHub Container Registry (GHCR) para imagenes inmutables.
- VPS Hostinger con Ubuntu 24.04.
- Nginx y Certbot instalados en el host.
- Docker Compose para frontend, backend, email-worker y PostgreSQL/pgvector.

Datos del entorno:

| Elemento | Valor |
|---|---|
| URL | `https://skillmatch.jabejarano.tech` |
| VPS | `72.62.235.87` |
| Usuario | `deploy` |
| Proyecto | `/srv/apps/skillmatch-ai` |
| Backups | `/srv/backups/skillmatch-ai/postgres` |
| Workflow | `.github/workflows/deploy.yml` |
| Script | `scripts/deploy-production.sh` |

El sistema no implementa rollback ni restauracion automatica de PostgreSQL.

## 2. Arquitectura

```text
push main / workflow_dispatch
        |
        v
GitHub Actions
  |-- backend-tests
  |-- frontend-tests
  `-- build-and-push
             |
             v
       GHCR (tags SHA)
             |
             v
deploy por SSH -> VPS -> docker compose pull
                         |
                         v
              backup -> Alembic -> up -d
                         |
                         v
                 health checks publicos
```

Nginx continua siendo el unico punto de entrada publico:

- `/` se reenvia a `127.0.0.1:8080`.
- `/api/` se reenvia a `127.0.0.1:8001`.
- PostgreSQL conserva solamente su puerto interno `5432/tcp`.

## 3. Jobs del workflow

### `validate-ref`

Impide desplegar produccion desde una referencia distinta de `main`.

### `backend-tests`

Conserva ese nombre por compatibilidad, pero actua como una validacion completa:

1. Levanta PostgreSQL 16 con pgvector como servicio temporal.
2. Configura `ENVIRONMENT=test` y una `DATABASE_URL` exclusiva del job.
3. Instala el backend mediante `pip install -e ".[dev]"`.
4. Comprueba que `app` puede importarse.
5. Ejecuta `alembic upgrade head` contra la base temporal.
6. Ejecuta los tests de `backend/tests` y `tests`.
7. Ejecuta Ruff y `pip check`.
8. Ejecuta `alembic check`.

Este job no conoce ni utiliza `DATABASE_URL` de produccion.

### `frontend-tests`

Tambien conserva su nombre, aunque actua como validacion completa:

1. Ejecuta `npm ci`.
2. Ejecuta los tests Angular.
3. Construye el frontend.
4. Ejecuta `npm audit --omit=dev --audit-level=high`.

### `build-and-push`

Docker Buildx construye y publica:

```text
ghcr.io/<owner>/skillmatch-ai-backend:<sha>
ghcr.io/<owner>/skillmatch-ai-frontend:<sha>
```

El owner se obtiene de GitHub y se normaliza a minusculas. Cada imagen recibe:

- SHA completo;
- SHA corto de 12 caracteres;
- tag `main`.

`email-worker` reutiliza la imagen backend. El despliegue usa el SHA completo,
no el tag mutable `main`.

### `deploy`

1. Valida los secrets requeridos.
2. Configura SSH usando `VPS_KNOWN_HOSTS`.
3. Inicia sesion temporalmente en GHCR mediante `GITHUB_TOKEN` y
   `--password-stdin`.
4. Ejecuta `git fetch`, `git checkout main` y `git merge --ff-only`.
5. Comprueba que `HEAD` coincide con `DEPLOY_SHA`.
6. Ejecuta `scripts/deploy-production.sh`.
7. Ejecuta `docker logout` y elimina las credenciales temporales.

La configuracion GHCR temporal se guarda en `/dev/shm` y no persiste tras el
job.

## 4. Comportamiento del script de despliegue

`scripts/deploy-production.sh`:

1. Valida argumentos, rutas, permisos y archivos requeridos.
2. Escribe `.env.deploy` en un archivo temporal.
3. Valida las dos referencias GHCR y mueve el archivo de forma atomica.
4. Usa siempre `.env.prod` y `.env.deploy` con ambos archivos Compose.
5. Ejecuta `docker compose pull`; no construye imagenes en el VPS.
6. Comprueba que el backend puede escribir en el volumen de uploads.
7. Crea un backup PostgreSQL predeploy.
8. Aborta si `pg_dump` falla o el dump pesa cero bytes.
9. Ejecuta `alembic upgrade head` con la imagen backend recien descargada.
10. Ejecuta `docker compose up -d --no-build`.
11. Comprueba backend, frontend y endpoints publicos.
12. Ejecuta solamente `docker image prune -f`.

No elimina volumenes, `/srv/data`, uploads o backups. Tampoco restaura la base de
datos ni revierte contenedores.

## 5. Secrets de GitHub Actions

Configurar en `Settings > Secrets and variables > Actions`:

| Secret | Formato |
|---|---|
| `VPS_HOST` | IP o hostname sin protocolo, usuario ni puerto |
| `VPS_USER` | `deploy` |
| `VPS_SSH_KEY` | Clave privada exclusiva de CI, sin passphrase |
| `VPS_KNOWN_HOSTS` | Linea verificada de known_hosts del VPS |

Para este VPS, `VPS_HOST` contiene solo `72.62.235.87`. No debe incluir
`http://`, `ssh://`, `deploy@` ni `:22`.

No copiar secrets en issues, commits, logs o documentacion.

## 6. Crear la clave SSH de CI desde Windows

En PowerShell:

```powershell
New-Item -ItemType Directory -Force "$env:USERPROFILE\.ssh"

ssh-keygen -t ed25519 -C "github-actions-skillmatch" -f "$env:USERPROFILE\.ssh\skillmatch_ci"
```

Cuando `ssh-keygen` solicite passphrase, pulsar Enter dos veces. GitHub Actions
no puede responder interactivamente a una passphrase.

Mostrar la clave publica que se instalara en el VPS:

```powershell
Get-Content "$env:USERPROFILE\.ssh\skillmatch_ci.pub"
```

Mostrar la clave privada exclusivamente para copiarla al secret
`VPS_SSH_KEY`:

```powershell
Get-Content "$env:USERPROFILE\.ssh\skillmatch_ci"
```

No compartir esa salida ni guardarla dentro del repositorio.

En el VPS, como `deploy`:

```bash
mkdir -p ~/.ssh
chmod 700 ~/.ssh
nano ~/.ssh/authorized_keys
chmod 600 ~/.ssh/authorized_keys
```

Pegar una linea completa de `skillmatch_ci.pub`, no la clave privada.

## 7. Configurar `VPS_KNOWN_HOSTS`

Obtener la clave publica del host desde una sesion ya confiable del VPS:

```bash
sudo awk '{print "72.62.235.87 "$1" "$2}' /etc/ssh/ssh_host_ed25519_key.pub
```

Guardar la linea resultante como secret `VPS_KNOWN_HOSTS`. Antes, comparar su
fingerprint por un canal confiable. El workflow no usa `ssh-keyscan` dinamico
como sustituto de esa verificacion.

## 8. Preparacion inicial del VPS

### Docker no interactivo

```bash
sudo visudo -f /etc/sudoers.d/deploy-docker
```

Contenido:

```text
deploy ALL=(root) NOPASSWD: /usr/bin/docker
```

Validacion:

```bash
sudo chmod 440 /etc/sudoers.d/deploy-docker
sudo visudo -cf /etc/sudoers.d/deploy-docker
sudo -n docker version
```

### Directorio de backups

```bash
ls -ld /srv/backups/skillmatch-ai/postgres
touch /srv/backups/skillmatch-ai/postgres/test_write
rm /srv/backups/skillmatch-ai/postgres/test_write
```

Estado esperado:

```text
drwxr-x--- deploy deploy /srv/backups/skillmatch-ai/postgres
```

### Permisos de uploads

```bash
sudo stat -c "%u:%g %a %n" /srv/data/skillmatch-ai/uploads
```

Estado esperado:

```text
999:999 750 /srv/data/skillmatch-ai/uploads
```

Correccion, solo si no coincide:

```bash
sudo chown -R 999:999 /srv/data/skillmatch-ai/uploads
sudo chmod -R 750 /srv/data/skillmatch-ai/uploads
```

### Repositorio

```bash
cd /srv/apps/skillmatch-ai
git status --short
git fetch origin main
```

El arbol versionado debe estar limpio. `.env.prod` y
`docker-compose.prod.override.yml` deben seguir locales y no versionados.

### SSH y firewalls

```bash
sudo ss -tlnp | grep ':22'
sudo ufw status verbose
```

Estado esperado:

- SSH en `0.0.0.0:22` y `[::]:22`.
- UFW permite `22/tcp` y `80,443/tcp`.
- UFW no permite publicamente `5432`, `8001` o `8080`.

Puede existir otra capa en el firewall de Hostinger. En este despliegue no habia
ningun firewall activo asociado en el panel. Si se habilita, debe permitir TCP
`22`, `80` y `443`, y bloquear la exposicion de `5432`, `8001` y `8080`.

## 9. Ejecutar un despliegue manual desde Actions

1. Abrir la pestana `Actions` del repositorio.
2. Seleccionar `Validate, build and deploy production`.
3. Pulsar `Run workflow`.
4. Seleccionar `main`.
5. Esperar a que todos los jobs terminen en verde.

La concurrencia usa el grupo `skillmatch-production` con
`cancel-in-progress: false`, por lo que dos despliegues no se ejecutan a la vez.

## 10. Comprobaciones postdeploy

```bash
cd /srv/apps/skillmatch-ai

git rev-parse --short HEAD
git status --short

cat .env.deploy

sudo docker compose --env-file .env.prod \
  --env-file .env.deploy \
  -f docker-compose.prod.yml \
  -f docker-compose.prod.override.yml \
  ps

curl -fsS http://127.0.0.1:8001/api/v1/health
curl -fsS -I http://127.0.0.1:8080
curl -fsS -I https://skillmatch.jabejarano.tech
curl -fsS https://skillmatch.jabejarano.tech/api/v1/health

ls -lh /srv/backups/skillmatch-ai/postgres | tail

sudo docker ps --format "table {{.Names}}\t{{.Ports}}"
```

`.env.deploy` solo debe contener las dos referencias GHCR por SHA; no contiene
secretos.

Puertos esperados:

```text
frontend  127.0.0.1:8080->80/tcp
backend   127.0.0.1:8001->8000/tcp
db        5432/tcp interno, sin publicacion host
```

No deben aparecer `0.0.0.0:5432`, `0.0.0.0:8001` o `0.0.0.0:8080`.

## 11. Consultar logs

```bash
sudo docker compose --env-file .env.prod \
  --env-file .env.deploy \
  -f docker-compose.prod.yml \
  -f docker-compose.prod.override.yml \
  logs --tail=100 backend

sudo docker compose --env-file .env.prod \
  --env-file .env.deploy \
  -f docker-compose.prod.yml \
  -f docker-compose.prod.override.yml \
  logs --tail=100 frontend

sudo docker compose --env-file .env.prod \
  --env-file .env.deploy \
  -f docker-compose.prod.yml \
  -f docker-compose.prod.override.yml \
  logs --tail=100 email-worker
```

## 12. Backups predeploy

Cada despliegue correcto crea antes de Alembic:

```text
/srv/backups/skillmatch-ai/postgres/skillmatch_predeploy_<fecha>_<sha-corto>.sql
```

Comprobar los ultimos dumps:

```bash
ls -lh /srv/backups/skillmatch-ai/postgres | tail
```

Los dumps pueden contener emails, perfiles y datos derivados de CVs. No deben
subirse a Git ni compartirse sin proteccion.

## 13. Troubleshooting real

### Instalacion editable del backend

Error:

```text
Multiple top-level packages discovered in a flat-layout: ['app', 'alembic']
```

Causa: `app/` y `alembic/` estaban al mismo nivel y setuptools no tenia una
regla explicita de descubrimiento.

Solucion aplicada en `backend/pyproject.toml`:

```toml
[build-system]
requires = ["setuptools>=69"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
where = ["."]
include = ["app*"]
exclude = ["alembic*", "tests*"]
```

`app*` es el paquete instalable. `alembic/` permanece en su ubicacion como
directorio de migraciones; no se movieron migraciones ni se cambio logica.

### Timeout en el primer SSH

Error:

```text
ssh: connect to host *** port 22: Connection timed out
```

Causas probables:

- timeout puntual entre el runner de GitHub Actions y el VPS;
- problema temporal de red o proveedor;
- `VPS_HOST` incorrecto o con un formato no valido;
- puerto 22 bloqueado por UFW o por el firewall Hostinger.

No era el error habitual de una clave incorrecta, que seria
`Permission denied (publickey)`, ni de known_hosts, que seria
`Host key verification failed`.

Comprobaciones en el VPS:

```bash
sudo ss -tlnp | grep ':22'
sudo ufw status verbose
```

Comprobaciones desde Windows:

```powershell
Test-NetConnection 72.62.235.87 -Port 22
ssh -i "$env:USERPROFILE\.ssh\skillmatch_ci" deploy@72.62.235.87
```

La solucion aplicada fue `Re-run failed jobs`; el segundo intento termino en
`Success`. Si vuelve a ocurrir de forma aislada y las comprobaciones son
correctas, repetir primero el job fallido. Si se repite, revisar `VPS_HOST`, UFW,
firewall Hostinger, disponibilidad del puerto 22 y conectividad del proveedor.

`Enable debug logging` solo amplia los logs; no corrige la conectividad.

## 14. Estado validado

La ejecucion final termino correctamente:

- `validate-ref`: correcto.
- `backend-tests`: correcto.
- `frontend-tests`: correcto.
- `build-and-push`: correcto.
- `deploy`: correcto.
- Estado global: `Success`.

Los nombres `backend-tests` y `frontend-tests` se conservan, aunque ambos jobs
realizan validacion integral. No se renombran para evitar cambios innecesarios en
el workflow ya validado.

## 15. Limites de esta fase

El sistema deliberadamente:

- no implementa rollback automatico;
- no restaura automaticamente PostgreSQL;
- no construye imagenes en el VPS;
- no modifica `.env.prod`;
- no expone PostgreSQL publicamente;
- no elimina backups, uploads o volumenes persistentes.
