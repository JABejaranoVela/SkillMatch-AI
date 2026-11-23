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
| Workflows | [CI](../.github/workflows/ci.yml), [releases](../.github/workflows/release.yml) y [despliegue](../.github/workflows/deploy.yml) |
| Script | `scripts/deploy-production.sh` |

El sistema no implementa rollback ni restauracion automatica de PostgreSQL.
El monitor de Brevo y `email_outbox` se instaló manualmente en el host y se
opera por separado del pipeline; ver [despliegue en VPS](deployment-vps.md#18-monitor-de-correo-y-alertas-telegram).

## 2. Arquitectura

La CI valida los pushes a `development` y las Pull Requests con destino a
`development` o `main`. Ejecuta las pruebas de backend, frontend y monitor
con permisos de lectura. Las PR también validan el título Conventional Commit.

Un push a `main` puede actualizar la PR de Release Please o publicar el tag y
la GitHub Release de una PR de release fusionada. La publicación de imágenes
y el despliegue empiezan con una solicitud manual independiente desde `main`.

```text
workflow_dispatch en main (tag publicado)
        |
        v
validate-release
  |
  v
quality-checks (backend, frontend, monitor)
  |
  v
build-and-push
             |
             v
       GHCR (versión, SHA y digest)
             |
             v
aprobación en production -> SSH -> docker compose pull por digest
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

### `validate-release`

Exige que el despliegue esté habilitado, un tag SemVer estable en `main`, una
GitHub Release publicada por el bot y su PR de Release Please fusionada.
El tag debe coincidir con el manifiesto y `version.txt` del mismo commit.
`quality-checks` repite las pruebas sobre el SHA verificado antes del build.

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

### `monitor-tests`

Ejecuta las pruebas unitarias de `ops/test_email_monitor.py` con diagnósticos
y Telegram simulados. También ejecuta las regresiones de despliegue y de
procedencia de releases con Git, Docker y GitHub simulados. Comprueba
`bash`, `flock` y `jq` antes de arrancar esas pruebas. Si falta una herramienta
o falla una prueba, el job falla también.

### `build-and-push`

Docker Buildx construye y publica:

```text
ghcr.io/<owner>/skillmatch-ai-backend:vX.Y.Z-<sha>-<run_id>.<run_attempt>
ghcr.io/<owner>/skillmatch-ai-frontend:vX.Y.Z-<sha>-<run_id>.<run_attempt>
```

Las etiquetas OCI registran la versión y el SHA completo. Cada intento tiene
un tag de imagen distinto. El VPS descarga los digests emitidos por Buildx y
`email-worker` reutiliza el digest del backend.

### `deploy`

Tras aprobar el entorno `production`, el job comprueba su configuración y
se conecta al VPS por SSH. Comprueba de nuevo el tag contra `origin/main`,
selecciona el SHA exacto con un checkout separado de la rama y ejecuta
`scripts/deploy-release.sh`. Un bloqueo local serializa los intentos mientras
se ejecuta `deploy-production.sh`.

El registro en `/srv/backups/skillmatch-ai/postgres/.release-deployments` conserva
versión, SHA y ambos digests. Un reintento solo se acepta sin aplicar cambios
si corresponde a la última release completada, los contenedores siguen
ejecutando sus imágenes, `.env.deploy` contiene esos mismos digests y no existe
un registro `pending`. El checkout del VPS también debe estar limpio y en el
SHA exacto del recibo. Una discrepancia de Git bloquea el reintento y requiere
reconciliación manual. El script verifica los contenedores y la configuración
guardada antes de registrar la finalización del despliegue.

Antes del primer intento de cada release, el script guarda en
`<tag>.previous-env` los digests de los contenedores en ejecución. El snapshot
no se sobrescribe al reintentar. Un intento interrumpido conserva `pending` y
bloquea nuevos despliegues. Antes de archivar ese marcador, reconcilia los
contenedores, Alembic, el backup y los health checks. Si los contenedores aún
sirven la release anterior, restaura o repara `.env.deploy` con los digests
comprobados del recibo anterior o del snapshot. Si Git quedó en el SHA del
intento fallido, conserva las modificaciones inesperadas y restaura el
checkout al SHA exacto de la release recuperada con `git checkout --detach`.
Usa el SHA del recibo de esa release o el SHA verificado del despliegue previo
si todavía no hay un recibo. Comprueba que `git rev-parse --verify HEAD`
devuelve ese SHA y que `git status --porcelain=v1 --untracked-files=all` queda
vacío. Verifica también que las referencias de `.env.deploy` coincidan con
las imágenes en ejecución y que Compose acepte la configuración con ese
checkout. Archiva `pending` solo después de esas comprobaciones. Para
reintentar la misma release, los contenedores deben volver a coincidir con
el snapshot original. Si no puedes verificar los digests o el checkout
recuperado, detén la operación y conserva `pending`.

El script etiqueta localmente ambos digests del snapshot antes del despliegue
y los de la release activa antes de cerrar `pending`. Usa las etiquetas
`skillmatch-retained/backend:sha256-<hex>` y
`skillmatch-retained/frontend:sha256-<hex>`, y compara el ID de cada etiqueta
con el del digest local. Esto protege las imágenes incluso en el almacén
clásico de Docker. Si falla la verificación de rollback, el despliegue se
detiene y conserva el estado previo. Antes de un rollback manual, verifica la
compatibilidad del esquema y que los IDs de las etiquetas locales correspondan
a los digests del snapshot. Para una recuperación sin GHCR, usa esas imágenes
locales con Compose configurado para no descargar ni construir imágenes.

#### Limpieza manual de imágenes obsoletas

Comprueba el espacio con `sudo -n docker system df -v` antes del despliegue.
En el almacén clásico, quitar una etiqueta puede eliminar también digests
del mismo repositorio. Las etiquetas `skillmatch-retained/…` pertenecen a
repositorios distintos de las referencias GHCR, por lo que quitar la etiqueta
local puede dejar el digest y la imagen en disco. Verifica el resultado con
el almacén instalado. [Docker Image Remove](https://docs.docker.com/reference/cli/docker/image/rm/)
· [Implementación del almacén clásico](https://github.com/moby/moby/blob/v28.5.2/daemon/images/image_delete.go#L129-L159)

1. En una sesión de mantenimiento autorizada, mantén el mismo bloqueo
   `flock` del despliegue sobre
   `/srv/backups/skillmatch-ai/postgres/.release-deployments/lock` durante toda
   la revisión y retirada. Si existe `pending` o no puedes adquirir el
   bloqueo, pospón la limpieza hasta reconciliar el estado.
2. Elige una release obsoleta desde su recibo. Para cada servicio, inventaría
   el ID completo y todas sus referencias locales con
   `sudo -n docker image inspect --format '{{.Id}} {{json .RepoTags}} {{json .RepoDigests}}' REF`.
   Comprueba que la etiqueta de retención y la referencia exacta
   `ghcr.io/…@sha256:…` corresponden al mismo ID. Registra también el espacio
   ocupado antes de retirar referencias.
3. Protege los IDs de la release activa según contenedores, `.env.deploy` y
   recibo, y los del último rollback válido y sus snapshots. Incluye todos
   los contenedores del host, también los detenidos que puedan usarse para
   recuperación. Usa `sudo -n docker ps -aq` para enumerarlos e inspecciona
   su campo `.Image`. Resuelve los digests protegidos a IDs de imagen para
   detectar referencias diferentes que compartan el mismo ID. Si falta
   información o cualquier referencia del candidato comparte un ID
   protegido, conserva la imagen y todas sus referencias.
4. Para un ID confirmado como obsoleto, retira únicamente su etiqueta local
   autorizada con `sudo -n docker image rm --no-prune "$etiqueta_obsoleta"`.
   Reinspecciona el ID y, si permanece el digest GHCR obsoleto, verifica que
   aún apunta al mismo ID antes de retirarlo con
   `sudo -n docker image rm --no-prune "$digest_obsoleto"`, donde la variable
   contiene la referencia completa `repositorio@sha256:…`. Conserva
   cualquier otro alias hasta revisarlo individualmente. Ante conflictos,
   detente y vuelve a comprobar el inventario. No uses `--force` ni un
   `prune` global.
5. Comprueba que las referencias retiradas ya no existen, si el ID sigue
   presente y cuánto cambió `sudo -n docker system df -v`. Distingue la
   retirada de un alias de la eliminación efectiva de la imagen. Las capas
   compartidas y las referencias conservadas pueden seguir ocupando espacio.

Las regresiones del despliegue se ejecutan en Linux con `bash`, `flock`, `jq` y
`python -B -m unittest discover -s ops -p 'test_*release.py' -v`.
Las pruebas simulan Git, Docker y los cambios de estado en directorios temporales.

La configuración temporal de GHCR se guarda en `/dev/shm` por intento y el
workflow intenta retirarla al terminar.

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

La limpieza de imágenes se gestiona por etiqueta de retención. El script
conserva las imágenes locales, los volúmenes, uploads y backups.

## 5. Activación y protección en GitHub

Mantén `RELEASE_AUTOMATION_ENABLED` y `PRODUCTION_RELEASES_ENABLED` sin definir
durante la primera integración en `main`. Antes de fusionar, comprueba que no
haya ejecuciones antiguas de despliegue pendientes. El nuevo workflow de
producción solo acepta `workflow_dispatch` desde `main` y ningún push publica
imágenes ni despliega.

1. En **Settings → Rules → Rulesets**, protege `main` con PR obligatoria,
   checks requeridos `pr-title`, `backend-tests`, `frontend-tests` y
   `monitor-tests`, rama actualizada antes del merge y bloqueo de borrado y
   force-push. Evita excepciones que permitan escribir directamente en
   `main`. Confirma los nombres tras observar los checks reales de GitHub
   Actions. Integra `development` con merge para conservar su historial de
   commits convencionales y sincroniza después `main` de vuelta.
2. En **Settings → Environments**, crea `production` con acceso solo a la
   rama `main`. Añade al desarrollador como revisor requerido, deja sin
   marcar **Prevent self-review** y deshabilita el bypass de administradores.
   Configura `PRODUCTION_ENV_READY=true` como variable del entorno, después
   de verificar la protección.
3. Mueve los cuatro secretos de VPS que aparecen abajo al ámbito del entorno
   `production` y retira las copias de nivel repositorio u organización. La
   protección depende de esa migración. Una PR interna que cambie YAML puede
   referenciar secretos de repositorio mientras sigan allí.
4. En **Settings → Actions → General**, permite que GitHub Actions cree PR.
   Release Please usa `GITHUB_TOKEN`. Si GitHub deja la CI de la PR del bot
   pendiente de autorización, apruébala desde la PR y verifica sus cuatro
   checks. Si la configuración no ofrece esa aprobación, detén la release
   hasta autorizar una GitHub App acotada al repositorio. Al configurar la
   credencial de esa App en Release Please, registra también el login exacto
   de su bot en la variable de repositorio `RELEASE_PLEASE_APP_BOT`. El
   verificador admite ese login y `github-actions[bot]`, y exige que la
   release y su PR procedan de la misma identidad. Coordina el cambio de
   credencial entre releases. La App real y su credencial quedan pendientes.
   Los eventos de release no disparan el despliegue.
5. Verifica CodeQL en las dos ramas y en una PR de fork antes de añadir
   su regla al ruleset. El procedimiento figura en la sección 5.1.

La versión global se mantiene en `version.txt` y el manifiesto de Release
Please. `0.0.0` indica que aún no existe una release gestionada. La primera
versión propuesta es `0.1.0` y el changelog se genera a partir de los commits
Conventional Commit. El tag identifica el conjunto backend, frontend y monitor.

Para la primera release, habilita solo `RELEASE_AUTOMATION_ENABLED=true` como
variable de repositorio y deja que la siguiente integración revisada en `main`
prepare la PR. Verifica su versión, changelog, título y checks. Al autorizar su
merge, comprueba que se crea una única Release `v0.1.0` sin publicación de
imágenes. Finalmente habilita `PRODUCTION_RELEASES_ENABLED=true` como variable
de repositorio y, cuando se autorice producción, selecciona el tag en
**Deploy a production release**. Revisa los checks y aprueba `production`.

Configura estos secretos solo en el entorno `production`.

| Secret | Formato |
|---|---|
| `VPS_HOST` | IP o hostname sin protocolo, usuario ni puerto |
| `VPS_USER` | `deploy` |
| `VPS_SSH_KEY` | Clave privada exclusiva de CI, sin passphrase |
| `VPS_KNOWN_HOSTS` | Linea verificada de known_hosts del VPS |

Para este VPS, `VPS_HOST` contiene solo `72.62.235.87`. No debe incluir
`http://`, `ssh://`, `deploy@` ni `:22`.

No copiar secrets en issues, commits, logs o documentacion.

### 5.1. Verificar CodeQL Advanced Setup y proteger el merge

[El workflow de CodeQL](../.github/workflows/codeql.yml) analiza Python,
JavaScript/TypeScript y los workflows de GitHub Actions con las consultas
estándar. Se ejecuta en pushes y PR hacia `development` y `main`. Los martes
a las 04:23 UTC repite el análisis de la rama predeterminada una vez que el
workflow esté integrado en ella. Cada lenguaje conserva su propia categoría.

1. Antes de publicar, comprueba en **Settings → Advanced Security → Code
   scanning** que Default Setup está desactivado y que ninguna otra integración
   envía resultados CodeQL para estas ramas. Usa el workflow versionado como
   única configuración. Mantén desactivadas las variables de release y producción
   durante el piloto.
2. Tras un push autorizado a `development`, abre **Actions → CodeQL** y verifica
   que los tres jobs terminan y que el paso **Analyze and upload results** sube
   los resultados. En **Security and quality → Code scanning**, comprueba la
   herramienta, la rama, el commit analizado y las categorías `/language:python`,
   `/language:javascript-typescript` y `/language:actions`. Revisa también
   la cobertura de archivos y los avisos de extracción de cada lenguaje.
3. Comprueba una PR interna hacia `development`, una de fork público hacia
   `development` y una PR abierta de `development` hacia `main`. Usa un cambio
   inocuo y actualiza la PR para verificar una segunda revisión. En **Checks**,
   confirma los tres resultados para el merge de prueba que GitHub asocia a la
   última revisión. El evento `pull_request` admite la carga de resultados del
   fork con su token restringido. Si GitHub pide aprobación para ejecutar el
   workflow de un colaborador externo, revisa el diff antes de autorizarlo.
   Mantén los permisos predeterminados del fork. El piloto termina con las PR
   abiertas o cerradas sin fusionar. El workflow antiguo de `main` puede seguir
   desplegando por push hasta integrar la transición de CI/CD.
4. Para ensayar el bloqueo antes de exigirlo en `main`, usa un repositorio
   público desechable con el mismo workflow, las mismas ramas y ejemplos
   sintéticos de los tres lenguajes. Aplica allí la regla del paso siguiente.
   Usa una muestra inerte que produzca una alerta High en el diff. Comprueba que
   bloquea el merge y que al corregirla en la misma PR se levanta el bloqueo.
   Si un análisis falla o falta una categoría, investiga la ejecución antes
   de aceptar el resultado.
5. Tras la primera integración autorizada, verifica la línea base de los tres
   lenguajes en el push a `main`. Una vez validado el piloto, edita **Protect main**
   en **Settings → Rules → Rulesets**. Añade **Require code scanning results**,
   elige **CodeQL**, fija el umbral de alertas de seguridad en **High or higher**
   y deja las alertas sin severidad de seguridad fuera del bloqueo automático.
   Conserva los cuatro checks de CI del punto 1 de la sección 5. La regla
   evalúa los hallazgos que GitHub atribuye al diff de la PR. Un job verde
   acredita que terminó el análisis y puede coexistir con una alerta bloqueante.

Las alertas nuevas **High** y **Critical** bloquean la integración con esa
regla. Revisa manualmente las **Medium**, **Low**, las de calidad y las alertas
preexistentes en la rama. Prioriza las que afecten a sesiones, acceso a CV o
permisos de workflows. Para descartar un falso positivo, registra en la alerta
la razón y la evidencia del flujo revisado.

[Protección de merge con CodeQL](https://docs.github.com/en/code-security/concepts/code-scanning/merge-protection)
· [Permisos de carga en PR](https://docs.github.com/en/code-security/reference/code-scanning/troubleshoot-analysis-errors/resource-not-accessible)

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

### Validaciones bloqueadas en octubre de 2026

Una ejecución anterior al commit `7960e78` superó las pruebas del backend y
frontend, pero se detuvo en dos controles posteriores:

- `ruff check` devolvió 66 errores al instalarse una versión nueva de Ruff con
  más reglas por defecto. `backend/pyproject.toml` declara ahora explícitamente
  las reglas `E4`, `E7`, `E9` y `F`; la comprobación con Ruff 0.17 pasó.
- `npm audit --omit=dev --audit-level=high` detectó 4 vulnerabilidades altas
  en el árbol de dependencias anterior. Los paquetes Angular se actualizaron
  conjuntamente a 20.3.32 y se regeneró `frontend/package-lock.json`; una
  instalación limpia y la auditoría local terminaron con 0 vulnerabilidades.

`build-and-push` y `deploy` se omitieron en aquella ejecución porque dependían
de ambos jobs de validación. No fue un fallo de arranque del VPS. Después se
observó en producción la imagen del commit correctivo `7960e78`, con los
contenedores saludables y los endpoints públicos respondiendo HTTP 200.

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
