# Despliegue de SkillMatch AI en VPS

Esta guia documenta el despliegue real de SkillMatch AI en un VPS Hostinger con
Ubuntu 24.04 LTS. No contiene secretos, contrasenas, claves API ni certificados.
Los valores sensibles deben existir solamente en el servidor.

## 1. Entorno desplegado

| Elemento | Valor |
|---|---|
| VPS | Hostinger, Ubuntu 24.04 LTS |
| IP publica | `72.62.235.87` |
| Usuario Linux | `deploy` |
| Repositorio | `SkillMatch-AI` |
| Codigo | `/srv/apps/skillmatch-ai` |
| Subdominio | `skillmatch.jabejarano.tech` |
| URL publica | `https://skillmatch.jabejarano.tech` |
| Entrada publica | Nginx del host en puertos 80 y 443 |
| HTTPS | Certbot y Let's Encrypt |
| Contenedores | frontend, backend, email-worker y PostgreSQL/pgvector |

Docker Engine y el plugin Docker Compose se ejecutan directamente en Linux. No
se utiliza Docker Desktop.

## 2. Arquitectura de produccion

```text
Internet
   |
   | HTTPS :443 / HTTP :80
   v
Nginx del VPS + Certbot
   |-- /      -> http://127.0.0.1:8080 -> frontend Nginx/Angular :80
   `-- /api/  -> http://127.0.0.1:8001 -> FastAPI :8000
                                              |
                         red privada Docker   |---- PostgreSQL 16 + pgvector
                                              `---- email_outbox
                                                        |
                                                        v
                                                 email-worker -> Brevo
```

- Nginx es el unico punto de entrada publico.
- El frontend se publica solo en `127.0.0.1:8080`.
- El backend se publica solo en `127.0.0.1:8001`.
- PostgreSQL no publica el puerto `5432` al host.
- El email-worker no publica puertos.
- UFW permite SSH y el perfil `Nginx Full`; no abre `5432`, `8001` ni `8080`.

## 3. Estructura persistente en `/srv`

```text
/srv/apps/skillmatch-ai/              codigo y archivos Compose
/srv/data/skillmatch-ai/postgres/     PGDATA persistente
/srv/data/skillmatch-ai/uploads/      CVs PDF persistentes
/srv/data/skillmatch-ai/tmp/          temporales operativos
/srv/data/skillmatch-ai/logs/         logs externos si se configuran
/srv/backups/skillmatch-ai/postgres/  dumps manuales de PostgreSQL
```

Creacion inicial:

```bash
sudo mkdir -p /srv/apps/skillmatch-ai
sudo mkdir -p /srv/data/skillmatch-ai/{postgres,uploads,tmp,logs}
sudo mkdir -p /srv/backups/skillmatch-ai/postgres
sudo chown -R deploy:deploy /srv/apps/skillmatch-ai
```

Los permisos de los directorios montados deben ajustarse al UID/GID real de cada
proceso dentro de su contenedor. En este despliegue el backend usa `999:999`; no
se debe asumir ese valor en otra imagen sin comprobarlo primero.

## 4. DNS

En la zona DNS de `jabejarano.tech` se creo un registro:

```text
Tipo: A
Nombre: skillmatch
Destino: 72.62.235.87
```

Antes de solicitar el certificado se comprobo la propagacion:

```bash
dig +short skillmatch.jabejarano.tech
```

El resultado debe incluir `72.62.235.87`.

## 5. Instalacion y verificacion de Docker

En Ubuntu se instalo Docker Engine y el plugin oficial de Compose. Un flujo
orientativo es:

```bash
sudo apt update
sudo apt install -y ca-certificates curl
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
  -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc

. /etc/os-release
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu ${UBUNTU_CODENAME:-$VERSION_CODENAME} stable" \
  | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io \
  docker-buildx-plugin docker-compose-plugin
sudo systemctl enable --now docker
```

Comprobaciones:

```bash
sudo docker version
sudo docker compose version
sudo systemctl status docker --no-pager
```

La etiqueta YAML `!override` requiere una version moderna de Docker Compose. El
VPS real se valido con Docker Compose `v5.2.0`.

## 6. Clonado del repositorio

```bash
cd /srv/apps
sudo -u deploy git clone URL_PRIVADA_O_PUBLICA_DEL_REPOSITORIO skillmatch-ai
cd /srv/apps/skillmatch-ai
git status --short
git branch --show-current
```

El despliegue debe realizarse desde la rama y revision previamente validadas. No
se debe copiar al servidor un directorio local con `.env`, backups o artefactos.

## 7. Configuracion de `.env.prod`

El archivo real se crea solo en el VPS y esta ignorado por Git:

```bash
cd /srv/apps/skillmatch-ai
cp .env.prod.example .env.prod
nano .env.prod
chmod 600 .env.prod
git check-ignore -v .env.prod
```

Variables principales:

| Variable | Configuracion de esta topologia |
|---|---|
| `ENVIRONMENT` | `production` |
| `DATABASE_URL` | URL interna hacia `db:5432`, con credenciales no predeterminadas |
| `SECRET_KEY` | Secreto aleatorio robusto, fuera de Git |
| `BACKEND_CORS_ORIGINS` | `["https://skillmatch.jabejarano.tech"]` |
| `FRONTEND_URL` | `https://skillmatch.jabejarano.tech` |
| `COOKIE_SECURE` | `true` |
| `TRUST_PROXY_HEADERS` | `true` solo en esta topologia de proxy controlado |
| `EMAIL_PROVIDER` | `brevo` |
| `BREVO_API_KEY` | Clave real almacenada solo en `.env.prod` |
| `EMAIL_PAYLOAD_ENCRYPTION_KEY` | Clave Fernet estable y exclusiva del entorno |

`TRUST_PROXY_HEADERS=true` no es un valor universal. Aqui es correcto porque
FastAPI solo escucha en `127.0.0.1:8001` y recibe trafico mediante el Nginx
controlado del host, que establece las cabeceras `X-Forwarded-*`. No debe
activarse si clientes no confiables pueden acceder directamente al backend o
inyectar esas cabeceras.

No se deben documentar ni versionar los valores reales de `SECRET_KEY`,
`POSTGRES_PASSWORD`, `BREVO_API_KEY` o `EMAIL_PAYLOAD_ENCRYPTION_KEY`.

## 8. Override local de produccion

La plantilla versionada se copia como archivo local:

```bash
cp docker-compose.prod.override.example.yml docker-compose.prod.override.yml
git check-ignore -v docker-compose.prod.override.yml
```

El override real monta los datos de `/srv` y limita los puertos al loopback:

```yaml
services:
  db:
    volumes:
      - /srv/data/skillmatch-ai/postgres:/var/lib/postgresql/data
      - ./docker/postgres/init.sql:/docker-entrypoint-initdb.d/init.sql:ro

  backend:
    ports: !override
      - "127.0.0.1:8001:8000"
    volumes:
      - /srv/data/skillmatch-ai/uploads:/app/storage/resumes

  email-worker:
    volumes:
      - /srv/data/skillmatch-ai/uploads:/app/storage/resumes

  frontend:
    ports: !override
      - "127.0.0.1:8080:80"
```

`ports: !override` reemplaza completamente la lista del Compose principal. Sin
esta etiqueta, Compose puede combinar `80:80` con `127.0.0.1:8080:80`, dejando
el puerto 80 ocupado por Docker y entrando en conflicto con Nginx.

Todos los comandos productivos deben incluir ambos archivos:

```bash
sudo docker compose --env-file .env.prod \
  -f docker-compose.prod.yml \
  -f docker-compose.prod.override.yml \
  config --quiet
```

`docker/postgres/init.sql` solo se ejecuta cuando PostgreSQL inicializa un
directorio `PGDATA` vacio. Modificarlo posteriormente no aplica cambios sobre
una base ya existente; para eso deben utilizarse migraciones Alembic.

## 9. Despliegue manual: build, base de datos y migraciones

Este procedimiento se conserva como alternativa manual. El flujo CI/CD descrito
en la seccion 17 construye las imagenes en GitHub Actions y evita compilar en el
VPS.

Construir las imagenes:

```bash
sudo docker compose --env-file .env.prod \
  -f docker-compose.prod.yml \
  -f docker-compose.prod.override.yml \
  build
```

Arrancar PostgreSQL y comprobar su estado:

```bash
sudo docker compose --env-file .env.prod \
  -f docker-compose.prod.yml \
  -f docker-compose.prod.override.yml \
  up -d db

sudo docker compose --env-file .env.prod \
  -f docker-compose.prod.yml \
  -f docker-compose.prod.override.yml \
  ps
```

Ejecutar Alembic manualmente antes de arrancar toda la aplicacion:

```bash
sudo docker compose --env-file .env.prod \
  -f docker-compose.prod.yml \
  -f docker-compose.prod.override.yml \
  run --rm backend alembic upgrade head
```

Arranque completo:

```bash
sudo docker compose --env-file .env.prod \
  -f docker-compose.prod.yml \
  -f docker-compose.prod.override.yml \
  up -d
```

## 10. Nginx del host

Nginx reenvia la SPA y la API sin exponer los contenedores directamente. El
archivo del virtual host puede ubicarse en
`/etc/nginx/sites-available/skillmatch-ai`:

```nginx
server {
    listen 80;
    listen [::]:80;
    server_name skillmatch.jabejarano.tech;

    location /api/ {
        proxy_pass http://127.0.0.1:8001;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Forwarded-Host $host;
    }

    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Forwarded-Host $host;
    }
}
```

El `proxy_pass` de `/api/` no incluye una ruta final que elimine el prefijo. De
este modo `/api/v1/health` llega al backend como `/api/v1/health`.

Activacion y validacion:

```bash
sudo ln -s /etc/nginx/sites-available/skillmatch-ai \
  /etc/nginx/sites-enabled/skillmatch-ai
sudo nginx -t
sudo systemctl reload nginx
```

## 11. HTTPS, Certbot y UFW

Con el registro DNS propagado y Nginx respondiendo por HTTP:

```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d skillmatch.jabejarano.tech
sudo certbot certificates
sudo certbot renew --dry-run
```

Reglas de firewall:

```bash
sudo ufw allow OpenSSH
sudo ufw allow 'Nginx Full'
sudo ufw status verbose
```

No se crean reglas para `5432`, `8001` ni `8080`.

La exposicion de red puede tener dos capas: UFW dentro de Ubuntu y el firewall
externo del proveedor. En este despliegue no habia un firewall activo asociado
en el panel de Hostinger. Si se habilita posteriormente, debe permitir solamente
TCP `22`, `80` y `443`; no debe publicar `5432`, `8001` ni `8080`.

## 12. Comprobaciones operativas

Estado de contenedores:

```bash
sudo docker compose --env-file .env.prod \
  -f docker-compose.prod.yml \
  -f docker-compose.prod.override.yml \
  ps
```

HTTP, HTTPS y API:

```bash
curl -I http://skillmatch.jabejarano.tech
curl -I https://skillmatch.jabejarano.tech
curl -fsS https://skillmatch.jabejarano.tech/api/v1/health
```

Puertos escuchando:

```bash
sudo ss -tulpn | grep -E ':8080|:8001|:5432|:80|:443'
```

El resultado esperado es Nginx en `0.0.0.0:80/443`, frontend en
`127.0.0.1:8080` y backend en `127.0.0.1:8001`. No debe aparecer PostgreSQL
escuchando publicamente en `0.0.0.0:5432`.

Logs principales:

```bash
sudo docker compose --env-file .env.prod \
  -f docker-compose.prod.yml \
  -f docker-compose.prod.override.yml \
  logs --tail=100 backend

sudo docker compose --env-file .env.prod \
  -f docker-compose.prod.yml \
  -f docker-compose.prod.override.yml \
  logs --tail=100 email-worker

sudo journalctl -u nginx --since "30 minutes ago"
```

## 13. Backup manual de PostgreSQL

La base debe estar arrancada. El dump se genera fuera del contenedor:

```bash
sudo mkdir -p /srv/backups/skillmatch-ai/postgres

set -o pipefail
BACKUP="/srv/backups/skillmatch-ai/postgres/skillmatch_$(date +%Y%m%d_%H%M%S).sql"
sudo docker compose --env-file .env.prod \
  -f docker-compose.prod.yml \
  -f docker-compose.prod.override.yml \
  exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB"' \
  | sudo tee "$BACKUP" > /dev/null
sudo test -s "$BACKUP"
```

Verificar que el archivo existe y no esta vacio:

```bash
sudo ls -lh /srv/backups/skillmatch-ai/postgres
```

Los dumps SQL pueden contener emails, perfiles, textos derivados de CVs y otros
datos personales. Deben protegerse, almacenarse fuera de Git y someterse a una
politica de acceso, cifrado y retencion.

## 14. Restauracion basica

La restauracion debe probarse primero en un entorno aislado. No se debe restaurar
sobre una base con datos sin confirmacion expresa y un backup previo.

```bash
cat /srv/backups/skillmatch-ai/postgres/backup_a_restaurar.sql \
  | sudo docker compose --env-file .env.prod \
      -f docker-compose.prod.yml \
      -f docker-compose.prod.override.yml \
      exec -T db sh -c 'psql -U "$POSTGRES_USER" "$POSTGRES_DB"'
```

Tras restaurar, ejecutar `alembic current`, revisar logs y repetir los smoke
tests antes de habilitar trafico.

## 15. Problemas reales resueltos

### 15.1 Conflicto del puerto 80

**Sintoma:** Docker intentaba publicar el frontend en `0.0.0.0:80`, pero Nginx
ya ocupaba ese puerto.

**Causa:** Docker Compose mezclaba la lista `ports` de
`docker-compose.prod.yml` con la del override local. Añadir otro puerto no
eliminaba necesariamente `80:80`.

**Solucion:** usar `ports: !override` en `docker-compose.prod.override.yml` para
reemplazar completamente la lista.

Resultado esperado:

```text
frontend: 127.0.0.1:8080 -> 80
backend:  127.0.0.1:8001 -> 8000
Nginx:    0.0.0.0:80 y 0.0.0.0:443
```

Comprobar la configuracion efectiva antes de arrancar:

```bash
sudo docker compose --env-file .env.prod \
  -f docker-compose.prod.yml \
  -f docker-compose.prod.override.yml \
  config
```

### 15.2 Error 500 al subir un PDF

**Sintoma en frontend:**

```text
Revisa que el archivo sea valido y vuelve a intentarlo.
```

**Consola del navegador:**

```text
api/v1/resumes/upload 500 Internal Server Error
```

**Log del backend:**

```text
PermissionError: [Errno 13] Permission denied: 'storage/resumes/1'
```

**Causa:** el backend del contenedor se ejecutaba como
`uid=999(skillmatch) gid=999(skillmatch)`, mientras el bind mount
`/srv/data/skillmatch-ai/uploads` pertenecia a `deploy`, normalmente
`1000:1000`.

**Solucion aplicada:**

```bash
sudo chown -R 999:999 /srv/data/skillmatch-ai/uploads
sudo chmod -R 750 /srv/data/skillmatch-ai/uploads
```

El UID debe comprobarse de nuevo si se reconstruye la imagen con otro usuario:

```bash
sudo docker compose --env-file .env.prod \
  -f docker-compose.prod.yml \
  -f docker-compose.prod.override.yml \
  exec backend id
```

Prueba de escritura:

```bash
sudo docker compose --env-file .env.prod \
  -f docker-compose.prod.yml \
  -f docker-compose.prod.override.yml \
  exec backend sh -c 'touch /app/storage/resumes/test_write && rm /app/storage/resumes/test_write && echo "uploads OK"'
```

## 16. Troubleshooting rapido

### Nginx devuelve 502

```bash
curl -fsS http://127.0.0.1:8080/health
curl -fsS http://127.0.0.1:8001/api/v1/health
sudo nginx -t
```

Revisar que ambos contenedores esten sanos y que el override publique los
puertos exclusivamente en localhost.

### El backend no arranca

Revisar `DATABASE_URL`, secretos obligatorios, CORS, cookies, Brevo y clave
Fernet. La configuracion productiva rechaza placeholders e HTTP/localhost en
los origenes publicos.

```bash
sudo docker compose --env-file .env.prod \
  -f docker-compose.prod.yml \
  -f docker-compose.prod.override.yml \
  logs --tail=200 backend
```

### El email no llega

Revisar el estado de `email-worker`, la API key de Brevo, el remitente verificado
y los registros SPF/DKIM/DMARC. No imprimir tokens ni payloads cifrados.

### PostgreSQL parece vacio

Confirmar que `/srv/data/skillmatch-ai/postgres` sigue montado y no se arranco el
servicio con otro override. No borrar ni reinicializar el directorio para intentar
recuperarlo.

## 17. Despliegue automatico con GitHub Actions

El CI/CD de produccion esta operativo mediante `.github/workflows/deploy.yml`.
Se ejecuta con cada push a `main` o manualmente con `workflow_dispatch` desde
esa misma rama.

```text
GitHub Actions -> validaciones -> build -> GHCR
                                      |
                                      v
VPS -> pull -> backup -> Alembic -> up -d -> health checks
```

- El backend y el frontend se construyen en GitHub Actions, no en el VPS.
- El VPS usa `.env.prod` y el `.env.deploy` generado para seleccionar imagenes
  inmutables por SHA.
- Antes de Alembic se exige un backup PostgreSQL no vacio.
- Los servicios mantienen frontend y backend ligados a localhost; PostgreSQL
  sigue sin puerto publicado.
- No hay rollback ni restauracion automatica.

La configuracion de secrets, claves SSH, preparacion inicial, comprobaciones,
logs e incidencias conocidas se mantiene en la guia principal:

**[CI/CD de produccion](ci-cd-production.md)**

## 18. Checklist final

- [ ] El registro crea un usuario pendiente.
- [ ] El email-worker envia el correo de verificacion.
- [ ] La verificacion activa la cuenta correcta.
- [ ] Login y logout funcionan sin reutilizar otra sesion.
- [ ] Se puede subir un PDF valido.
- [ ] Un PDF invalido se rechaza de forma segura.
- [ ] El CV se analiza y genera perfil profesional.
- [ ] Matching y recomendaciones responden correctamente.
- [ ] PostgreSQL conserva datos tras recrear los contenedores.
- [ ] El backend puede escribir en el volumen de uploads.
- [ ] HTTPS presenta un certificado valido.
- [ ] HTTP redirige a HTTPS.
- [ ] Los puertos `5432`, `8001` y `8080` no son publicos.
- [ ] Backend, frontend, worker y PostgreSQL no muestran errores criticos.
- [ ] Se creo y verifico un backup inicial fuera del repositorio.
