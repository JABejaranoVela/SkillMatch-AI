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

## 18. Monitor de correo y alertas Telegram

La aplicación usa la API HTTP de Brevo. El comando de diagnóstico del backend
consulta `GET https://api.brevo.com/v3/account` con la clave ya configurada y lee
solo estados e IDs de `email_outbox`. No envía correos ni modifica la cola. La
salida JSON no contiene destinatarios, tokens, payloads ni respuestas de Brevo.

El monitor del host ejecuta dos comprobaciones: API una vez al día a las 08:00
(hora local del VPS, UTC en la verificación del 14 de octubre de 2026) y outbox
cada cinco minutos. Detecta nuevos `failed`,
`pending` vencidos más de diez minutos, `sending` abandonados según
`EMAIL_WORKER_STALE_MINUTES`, worker detenido y consultas imposibles. Envía un
aviso por incidente y otro al recuperarse los estados transitorios. Un `failed`
es terminal y no genera aviso de recuperación. El estado de deduplicación queda
en `/srv/data/skillmatch-ai/tmp/email-monitor-state.json` con permisos privados.

### Instalación manual

Crear el bot con BotFather y obtener el ID del chat de alertas. Guardar ambos
valores **solo en el VPS**; evitar incluir el token en comandos, URLs del
historial de shell o logs. El usuario `deploy` debe conservar el permiso
`sudo -n docker` descrito en la guia de CI/CD. En el VPS actual, `install` y
`systemctl` requieren la contraseña de `sudo`: el operador ejecuta esos pasos
en su propia sesión, sin compartir la contraseña.

Para obtener el ID de un chat privado, abrir el bot en Telegram, pulsar
**Iniciar** y enviar `/start`. Desde PowerShell, introducir el token mediante
un prompt oculto y mostrar solo los IDs recibidos por `getUpdates`:

```powershell
$secure = Read-Host 'Token del bot' -AsSecureString
$ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
try {
  $token = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr)
  $updates = Invoke-RestMethod -Method Post `
    -Uri ("https://api.telegram.org/bot{0}/getUpdates" -f $token) `
    -Body @{ limit = 100; timeout = 0 } -ErrorAction Stop
  $updates.result | ForEach-Object {
    if ($_.message) { $_.message.chat.id }
  } | Sort-Object -Unique
} catch {
  Write-Host 'No se pudo consultar getUpdates.'
} finally {
  [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr)
  Remove-Variable token -ErrorAction SilentlyContinue
}
```

Si no aparece el ID, enviar otro mensaje al bot. `getUpdates` no funciona
mientras el bot tenga un webhook activo. No guardar el JSON completo ni poner
el token en una URL del navegador. Ver la [Bot API de Telegram](https://core.telegram.org/bots/api#getupdates).

```bash
sudo install -d -m 700 -o deploy -g deploy /etc/skillmatch-ai
sudo install -m 600 -o deploy -g deploy /dev/null /etc/skillmatch-ai/email-monitor.env
sudo chown deploy:deploy /srv/data/skillmatch-ai/tmp
sudo chmod 700 /srv/data/skillmatch-ai/tmp
sudo -u deploy nano /etc/skillmatch-ai/email-monitor.env
```

Contenido del archivo local (sustituir los marcadores allí, no en Git):

```text
TELEGRAM_BOT_TOKEN=VALOR_LOCAL_DEL_BOT
TELEGRAM_CHAT_ID=ID_LOCAL_DEL_CHAT
```

Verificar `chmod 600 /etc/skillmatch-ai/email-monitor.env`. El monitor rechaza
permisos que permitan acceso al grupo u otros usuarios. No introducir estas
variables en `.env.prod`, Docker Compose ni las unidades systemd.

Primero enviar una alerta de prueba y ejecutar ambas comprobaciones manuales:

```bash
cd /srv/apps/skillmatch-ai
sudo -u deploy python3 ops/email_monitor.py test
sudo -u deploy python3 ops/email_monitor.py api
sudo -u deploy python3 ops/email_monitor.py outbox
```

La prueba debe llegar al chat. Si alguna comprobación detecta un problema,
puede enviar una alerta real; revisar `email-worker`, Brevo y los conteos antes
de activar los temporizadores. La consulta directa al contenedor también sirve
para inspeccionar el JSON sin credenciales en la salida:

```bash
sudo docker compose --env-file .env.prod --env-file .env.deploy \
  -f docker-compose.prod.yml -f docker-compose.prod.override.yml \
  exec -T backend python -m app.commands.email_diagnostics outbox
```

Instalar las unidades después de la prueba:

```bash
sudo install -m 644 ops/systemd/skillmatch-email-api.service /etc/systemd/system/
sudo install -m 644 ops/systemd/skillmatch-email-api.timer /etc/systemd/system/
sudo install -m 644 ops/systemd/skillmatch-email-outbox.service /etc/systemd/system/
sudo install -m 644 ops/systemd/skillmatch-email-outbox.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now skillmatch-email-api.timer skillmatch-email-outbox.timer
systemctl list-timers 'skillmatch-email-*'
```

Comprobar además `systemctl is-enabled` y `systemctl is-active` para ambos
temporizadores. Los servicios son de tipo `oneshot`; entre ejecuciones pueden
figurar como `inactive`, pero su último `Result` debe ser `success` y
`ExecMainStatus` debe valer `0`:

```bash
systemctl show skillmatch-email-api.service skillmatch-email-outbox.service \
  -p Id -p Result -p ExecMainStatus -p ActiveState --no-pager
```

Para revisar ejecución y detener la automatización:

```bash
sudo journalctl -u skillmatch-email-api.service -u skillmatch-email-outbox.service --since today
sudo systemctl disable --now skillmatch-email-api.timer skillmatch-email-outbox.timer
```

Tras instalarla, probar una recuperación de contraseña con una cuenta de prueba:
confirmar que la fila de outbox llega a `sent`, que el correo se recibe en el
buzón controlado y que no aparece ninguna alerta. No consultar ni registrar el
token ni el contenido del mensaje.

### Puesta en marcha verificada el 14 de octubre de 2026

- La imagen desplegada correspondía al commit `7960e78`; frontend y API pública
  respondieron HTTP 200, backend/frontend/db estaban saludables y `email-worker`
  seguía activo.
- El diagnóstico de `GET /v3/account` de Brevo devolvió HTTP 200. Las 8 pruebas
  del monitor con diagnósticos y Telegram simulados pasaron; las pruebas de
  respuestas HTTP de Brevo están en `tests/test_email_diagnostics.py`.
- El archivo local de Telegram y el estado de deduplicación tenían permisos
  `600`; el directorio de estado, `700`. El token y el ID del chat no se
  incorporaron al repositorio ni se imprimieron durante las comprobaciones.
- El usuario confirmó la recepción de dos mensajes: alerta de prueba y aviso
  inicial por tres filas `failed` existentes. Esas filas permanecen; el monitor
  conserva sus IDs para no repetir el mismo aviso en cada ciclo.
- Ambos temporizadores quedaron `enabled` y `active`. La ejecución automática de
  outbox de las 10:45 UTC terminó con `Result=success` y `ExecMainStatus=0`;
  su siguiente ejecución quedó programada cinco minutos después.
- Se solicitó una recuperación de contraseña con cuenta de prueba. El correo
  llegó al buzón y el contador `sent` subió de 2 a 3. Había cero `pending`,
  cero `sending`, cero pendientes vencidos y cero envíos abandonados.

La comprobación diaria confirma que la clave de Brevo responde; no confirma
entrega en bandeja. Una prueba sintética con buzón controlado sería una fase
posterior. Si cae el VPS completo, sus temporizadores tampoco pueden alertar;
eso requiere un monitor externo. No se monitorizan SMTP ni MCP porque la
aplicación no los utiliza. Las unidades no forman parte del despliegue
automático y deben instalarse manualmente en el VPS.

## 19. Checklist final

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
