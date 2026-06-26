# Runbook de primer despliegue controlado / staging

Este runbook describe el primer despliegue controlado de SkillMatch AI en un
VPS o entorno real cerrado. No abre la aplicacion a usuarios reales y no debe
introducir secretos, certificados ni dominios reales en Git.

Objetivo: validar infraestructura, HTTPS, correo real, migraciones, backups y
flujos principales antes de pasar a una produccion cerrada.

## 1. Prerrequisitos

Antes de desplegar necesitas:

- VPS o servidor Linux con acceso SSH.
- Dominio o subdominio para staging.
- Nginx, Certbot, HTTPS y UFW funcionando en el host.
- Docker y Docker Compose instalados.
- Repositorio clonado desde una rama estable, normalmente `main`.
- Cuenta Brevo con API key creada fuera del repositorio.
- Remitente o dominio verificado en Brevo.
- DNS gestionable para crear registros A, SPF, DKIM y DMARC.
- Espacio fuera del contenedor para datos persistentes y backups.
- Variables secretas generadas fuera de Git.

No uses datos personales reales en las primeras pruebas. Usa una cuenta de
prueba y un CV ficticio o de prueba.

## 2. Estructura recomendada en el VPS

Usa nombres consistentes con el proyecto:

```text
/srv/apps/skillmatch-ai
/srv/data/skillmatch-ai/postgres
/srv/data/skillmatch-ai/uploads
/srv/data/skillmatch-ai/tmp
/srv/data/skillmatch-ai/logs
/srv/backups/skillmatch-ai/postgres
```

Responsabilidades:

- `/srv/apps/skillmatch-ai`: repo Git y archivos versionados.
- `/srv/data/skillmatch-ai/postgres`: datos fisicos de PostgreSQL.
- `/srv/data/skillmatch-ai/uploads`: CVs subidos por usuarios.
- `/srv/data/skillmatch-ai/tmp`: espacio temporal operativo si se necesita.
- `/srv/data/skillmatch-ai/logs`: logs externos si se decide montarlos.
- `/srv/backups/skillmatch-ai/postgres`: backups generados con `pg_dump`.

No guardes bases de datos, CVs, backups, certificados ni `.env.prod` dentro de
Git.

## 3. Dominio recomendado

Para el primer despliegue controlado usa un subdominio:

```text
https://staging.DOMINIO_REAL
```

Es preferible a usar el dominio raiz porque permite validar configuracion,
emails y backups sin mezclar staging con la futura produccion publica.

Valores esperados en `.env.prod`:

```env
FRONTEND_URL=https://staging.DOMINIO_REAL
BACKEND_CORS_ORIGINS=["https://staging.DOMINIO_REAL"]
COOKIE_SECURE=true
COOKIE_SAMESITE=lax
```

No inventes ni versiones dominios reales. Sustituye `DOMINIO_REAL` solo en el
servidor.

## 4. Preparar el VPS

Comandos orientativos para un servidor Debian/Ubuntu. Revisa cada comando antes
de ejecutarlo en tu entorno.

```bash
sudo apt update
sudo apt install -y ca-certificates curl git
docker --version
docker compose version
nginx -v
certbot --version
sudo ufw status
```

Crear carpetas:

```bash
sudo mkdir -p /srv/apps
sudo mkdir -p /srv/data/skillmatch-ai/postgres
sudo mkdir -p /srv/data/skillmatch-ai/uploads
sudo mkdir -p /srv/data/skillmatch-ai/tmp
sudo mkdir -p /srv/data/skillmatch-ai/logs
sudo mkdir -p /srv/backups/skillmatch-ai/postgres
sudo chown -R "$USER:$USER" /srv/apps /srv/backups/skillmatch-ai
```

No fijes permisos de PostgreSQL o uploads a ciegas. Primero construye/arranca y
comprueba los usuarios reales si aparece un error de permisos:

```bash
docker compose --env-file .env.prod \
  -f docker-compose.prod.yml \
  -f docker-compose.prod.override.yml \
  exec backend id

docker compose --env-file .env.prod \
  -f docker-compose.prod.yml \
  -f docker-compose.prod.override.yml \
  exec db id postgres
```

La imagen real de base de datos es `pgvector/pgvector:pg16`. Si PostgreSQL no
puede escribir en `/srv/data/skillmatch-ai/postgres`, revisa logs y ajusta
permisos con el UID/GID real observado, no con valores asumidos.

## 5. Clonar el proyecto

```bash
cd /srv/apps
git clone URL_DEL_REPOSITORIO skillmatch-ai
cd /srv/apps/skillmatch-ai
git checkout main
git pull
git status --short
```

Comprueba que `.env.prod` y el override real no se versionan:

```bash
git check-ignore -v .env.prod
git check-ignore -v docker-compose.prod.override.yml
```

Si alguno no muestra una regla de ignore, no continues hasta corregirlo.

## 6. Crear `.env.prod`

Copia el ejemplo y editalo en el servidor:

```bash
cp .env.prod.example .env.prod
nano .env.prod
```

Variables minimas a rellenar:

```env
ENVIRONMENT=production
DATABASE_URL=postgresql+psycopg://USUARIO:PASSWORD@db:5432/BASE
SECRET_KEY=REPLACE_WITH_STRONG_SECRET_KEY
FRONTEND_URL=https://staging.DOMINIO_REAL
BACKEND_CORS_ORIGINS=["https://staging.DOMINIO_REAL"]
COOKIE_SECURE=true
COOKIE_SAMESITE=lax
EMAIL_PROVIDER=brevo
BREVO_API_KEY=REPLACE_WITH_BREVO_API_KEY
EMAIL_FROM=noreply@DOMINIO_VERIFICADO
EMAIL_PAYLOAD_ENCRYPTION_KEY=REPLACE_WITH_FERNET_KEY
POSTGRES_USER=REPLACE_WITH_DB_USER
POSTGRES_PASSWORD=REPLACE_WITH_DB_PASSWORD
POSTGRES_DB=REPLACE_WITH_DB_NAME
```

Generar `SECRET_KEY` fuera de Git:

```bash
python3 - <<'PY'
import secrets
print(secrets.token_urlsafe(48))
PY
```

Generar `EMAIL_PAYLOAD_ENCRYPTION_KEY` fuera de Git:

```bash
python3 - <<'PY'
from cryptography.fernet import Fernet
print(Fernet.generate_key().decode())
PY
```

Si `cryptography` no esta disponible en el host, genera la clave en una maquina
segura o en un entorno temporal local. No la pegues en commits, tickets ni logs.

Generar password de PostgreSQL fuera de Git:

```bash
python3 - <<'PY'
import secrets
print(secrets.token_urlsafe(32))
PY
```

## 7. Override local de produccion

El archivo versionado `docker-compose.prod.override.example.yml` es una
plantilla para VPS. Copialo en el servidor como override real:

```bash
cp docker-compose.prod.override.example.yml docker-compose.prod.override.yml
nano docker-compose.prod.override.yml
```

El override real debe quedar fuera de Git. Docker Compose no lo cargara si
ejecutas solo `-f docker-compose.prod.yml`. Cuando uses el override, incluye
ambos archivos en todos los comandos.

Ejemplo de puertos para Nginx host:

```yaml
services:
  frontend:
    ports:
      - "127.0.0.1:8080:80"
```

Si Nginx host va a proxyear directamente a FastAPI, puedes exponer backend solo
en localhost:

```yaml
services:
  backend:
    ports:
      - "127.0.0.1:8001:8000"
```

Si Nginx host solo proxya al frontend en `127.0.0.1:8080`, y el Nginx del
contenedor frontend proxya `/api/` internamente a `backend:8000`, el puerto
`8001` no es necesario.

PostgreSQL no debe publicar `5432` al host.

## 8. Nginx host como reverse proxy

El reverse proxy publico sera Nginx instalado en el host. El contenedor frontend
queda detras sirviendo HTTP interno.

Flujo recomendado:

```text
Internet -> Nginx host HTTPS -> 127.0.0.1:8080 -> frontend/Nginx contenedor -> backend interno
```

Ejemplo orientativo de server block en el host, no versionado:

```nginx
server {
    listen 443 ssl http2;
    server_name staging.DOMINIO_REAL;

    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto https;
        proxy_set_header X-Forwarded-Host $host;
    }
}
```

Requisitos:

- El A record de `staging.DOMINIO_REAL` apunta al VPS.
- UFW permite 80/443.
- Certbot gestiona certificados fuera del repo.
- No guardes certificados ni claves privadas en Git.
- No actives HSTS hasta validar HTTPS real y renovacion de certificados.

## 9. `init.sql` de PostgreSQL

`docker/postgres/init.sql` crea la extension `vector`:

```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

PostgreSQL solo ejecuta scripts de `/docker-entrypoint-initdb.d/` cuando
`/var/lib/postgresql/data` esta vacio. Si `/srv/data/skillmatch-ai/postgres`
ya contiene una base inicializada, `init.sql` no se vuelve a ejecutar al
reiniciar contenedores.

## 10. Brevo y DNS de correo

Checklist operativo:

- Crear API key en Brevo y guardarla solo en `.env.prod`.
- Verificar remitente o dominio remitente en Brevo.
- Configurar SPF.
- Configurar DKIM.
- Configurar DMARC.
- Comprobar que `EMAIL_FROM` pertenece al dominio verificado.
- Arrancar `email-worker`.
- Probar registro y recepcion del email de verificacion.
- Probar recuperacion de contrasena.
- Revisar logs del worker sin exponer tokens ni enlaces completos.

Comandos de logs con override:

```bash
docker compose --env-file .env.prod \
  -f docker-compose.prod.yml \
  -f docker-compose.prod.override.yml \
  logs -f email-worker
```

## 11. Build, migraciones y arranque

Build:

```bash
docker compose --env-file .env.prod \
  -f docker-compose.prod.yml \
  -f docker-compose.prod.override.yml \
  build
```

Arrancar solo base de datos:

```bash
docker compose --env-file .env.prod \
  -f docker-compose.prod.yml \
  -f docker-compose.prod.override.yml \
  up -d db
```

Migraciones:

```bash
docker compose --env-file .env.prod \
  -f docker-compose.prod.yml \
  -f docker-compose.prod.override.yml \
  run --rm backend alembic upgrade head
```

Arranque completo:

```bash
docker compose --env-file .env.prod \
  -f docker-compose.prod.yml \
  -f docker-compose.prod.override.yml \
  up -d
```

En un primer despliegue desde cero no hay backup previo util. Antes de futuras
migraciones, el backup sera obligatorio.

## 12. Estado, logs y mantenimiento

Estado:

```bash
docker compose --env-file .env.prod \
  -f docker-compose.prod.yml \
  -f docker-compose.prod.override.yml \
  ps
```

Logs:

```bash
docker compose --env-file .env.prod \
  -f docker-compose.prod.yml \
  -f docker-compose.prod.override.yml \
  logs -f frontend

docker compose --env-file .env.prod \
  -f docker-compose.prod.yml \
  -f docker-compose.prod.override.yml \
  logs -f backend

docker compose --env-file .env.prod \
  -f docker-compose.prod.yml \
  -f docker-compose.prod.override.yml \
  logs -f email-worker

docker compose --env-file .env.prod \
  -f docker-compose.prod.yml \
  -f docker-compose.prod.override.yml \
  logs -f db
```

Cleanup en modo simulacion:

```bash
docker compose --env-file .env.prod \
  -f docker-compose.prod.yml \
  -f docker-compose.prod.override.yml \
  run --rm backend python -m app.commands.cleanup --dry-run
```

Parada:

```bash
docker compose --env-file .env.prod \
  -f docker-compose.prod.yml \
  -f docker-compose.prod.override.yml \
  down
```

No uses `down -v` salvo que hayas confirmado que puedes borrar volumenes y
datos.

## 13. Backup y restauracion

La base debe estar arrancada antes de hacer backup:

```bash
docker compose --env-file .env.prod \
  -f docker-compose.prod.yml \
  -f docker-compose.prod.override.yml \
  up -d db

docker compose --env-file .env.prod \
  -f docker-compose.prod.yml \
  -f docker-compose.prod.override.yml \
  ps

mkdir -p /srv/backups/skillmatch-ai/postgres

docker compose --env-file .env.prod \
  -f docker-compose.prod.yml \
  -f docker-compose.prod.override.yml \
  exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB"' \
  > /srv/backups/skillmatch-ai/postgres/skillmatch_$(date +%Y%m%d_%H%M%S).sql
```

Restauracion orientativa:

```bash
cat /srv/backups/skillmatch-ai/postgres/backup_a_restaurar.sql | docker compose --env-file .env.prod \
  -f docker-compose.prod.yml \
  -f docker-compose.prod.override.yml \
  exec -T db sh -c 'psql -U "$POSTGRES_USER" "$POSTGRES_DB"'
```

Advertencias:

- No restaures sobre una base con datos sin confirmarlo expresamente.
- Prueba la restauracion en un entorno de prueba antes de depender de ella.
- No guardes backups en Git.
- Los backups contienen datos personales, CVs, emails, textos extraidos y datos
  derivados.
- En un primer despliegue desde cero no hay backup previo util.
- Antes de futuras migraciones, el backup sera obligatorio.

## 14. Smoke tests manuales

Haz estas pruebas con una cuenta de prueba y un CV ficticio o de prueba. No uses
datos personales reales al principio.

- Abrir `https://staging.DOMINIO_REAL`.
- Comprobar `/api/v1/health` a traves del dominio.
- Cargar landing.
- Registrar usuario de prueba.
- Recibir email de verificacion.
- Verificar cuenta.
- Hacer login.
- Subir PDF valido.
- Confirmar rechazo de PDF invalido.
- Buscar ofertas compatibles.
- Guardar una oferta.
- Descartar una oferta.
- Marcar una oferta como postulada.
- Borrar el CV.
- Solicitar recuperacion de contrasena.
- Restablecer contrasena.
- Revisar logs de `backend`, `frontend`, `db` y `email-worker`.

## 15. Rollback basico

Si algo falla:

1. No abras la aplicacion a usuarios.
2. Guarda logs relevantes.
3. Para servicios:

```bash
docker compose --env-file .env.prod \
  -f docker-compose.prod.yml \
  -f docker-compose.prod.override.yml \
  down
```

4. Si hubo migracion y necesitas volver atras, restaura un backup validado en
   un entorno controlado antes de hacerlo en el servidor real.
5. Si solo fallo la imagen, vuelve a la version anterior del repo o de la imagen
   y reconstruye.
6. No ejecutes `down -v` salvo que hayas confirmado que puedes borrar volumenes
   y datos.

## 16. Criterios para pasar a produccion cerrada

Antes de pasar de staging a una produccion cerrada debe cumplirse:

- HTTPS funcionando sin errores de certificado.
- Emails de verificacion y recuperacion entregados correctamente.
- SPF, DKIM y DMARC configurados.
- Backups generados y restauracion probada en entorno de prueba.
- Smoke tests completos sin errores criticos.
- Logs sin tracebacks repetidos ni errores de worker.
- Rendimiento aceptable para el volumen esperado.
- Politica legal y privacidad revisadas antes de usuarios reales.
- Plan de soporte y rollback conocido.

Mientras esos puntos no esten cerrados, el entorno debe considerarse staging.
