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
- Docker y Docker Compose instalados.
- Repositorio clonado desde una rama estable, normalmente `main`.
- Cuenta Brevo con API key creada fuera del repositorio.
- Remitente o dominio verificado en Brevo.
- DNS gestionable para crear registros A, SPF, DKIM y DMARC.
- Espacio fuera del contenedor para backups.
- Variables secretas generadas fuera de Git.

No uses datos personales reales en las primeras pruebas. Usa una cuenta de
prueba y un CV ficticio o de prueba.

## 2. Dominio recomendado

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

## 3. Preparar el VPS

Comandos orientativos para un servidor Debian/Ubuntu. Revisa cada comando antes
de ejecutarlo en tu entorno.

```bash
sudo apt update
sudo apt install -y ca-certificates curl git
docker --version
docker compose version
```

Clonar el proyecto:

```bash
mkdir -p ~/apps
cd ~/apps
git clone URL_DEL_REPOSITORIO SkillMatch-AI
cd SkillMatch-AI
git checkout main
git pull
git status --short
```

Comprueba que `.env.prod` no se versiona:

```bash
git check-ignore -v .env.prod
```

Si ese comando no muestra una regla de ignore, no continues hasta corregirlo.

## 4. Crear `.env.prod`

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

## 5. HTTPS y reverse proxy

La opcion preferente para staging en un VPS pequeno es usar Caddy en el host
como reverse proxy HTTPS. El contenedor frontend/Nginx queda detras, sirviendo
HTTP interno.

Flujo:

```text
Internet -> Caddy host HTTPS -> 127.0.0.1:8080 -> frontend/Nginx contenedor -> backend interno
```

Requisitos:

- El A record de `staging.DOMINIO_REAL` apunta al VPS.
- Los puertos 80 y 443 del host estan abiertos.
- Caddy esta instalado y activo en el host.
- Los certificados quedan fuera del repositorio.
- No actives HSTS hasta validar HTTPS real y estable.

Caddyfile orientativo, no versionado:

```caddyfile
staging.DOMINIO_REAL {
    reverse_proxy 127.0.0.1:8080
}
```

Alternativa clasica: Nginx instalado en el host como reverse proxy. Es valida,
pero requiere configurar certificados, renovacion y proxy manualmente.

## 6. Override local de produccion

Por defecto `docker-compose.prod.yml` publica el frontend en `80:80`. Si usas
Caddy o Nginx en el host, crea un override local no versionado:

```yaml
# docker-compose.prod.override.yml
services:
  frontend:
    ports:
      - "127.0.0.1:8080:80"
```

Este archivo esta ignorado por Git. Docker Compose no lo cargara si ejecutas
solo `-f docker-compose.prod.yml`. Cuando uses el override, incluye ambos
archivos en todos los comandos.

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

Estado, logs y parada:

```bash
docker compose --env-file .env.prod \
  -f docker-compose.prod.yml \
  -f docker-compose.prod.override.yml \
  ps

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
  down
```

Para `exec` y `run`, usa el mismo patron de archivos:

```bash
docker compose --env-file .env.prod \
  -f docker-compose.prod.yml \
  -f docker-compose.prod.override.yml \
  exec backend python -m app.commands.cleanup --dry-run
```

## 7. Brevo y DNS de correo

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

Comandos de logs:

```bash
docker compose --env-file .env.prod -f docker-compose.prod.yml logs -f email-worker
docker compose --env-file .env.prod -f docker-compose.prod.yml logs -f backend
```

Si usas override local, incluye tambien `-f docker-compose.prod.override.yml`.

## 8. Build, migraciones y arranque

Primer despliegue o despliegue normal sin override:

```bash
docker compose --env-file .env.prod -f docker-compose.prod.yml build
docker compose --env-file .env.prod -f docker-compose.prod.yml up -d db
docker compose --env-file .env.prod -f docker-compose.prod.yml run --rm backend alembic upgrade head
docker compose --env-file .env.prod -f docker-compose.prod.yml up -d
```

Con override local:

```bash
docker compose --env-file .env.prod \
  -f docker-compose.prod.yml \
  -f docker-compose.prod.override.yml \
  build

docker compose --env-file .env.prod \
  -f docker-compose.prod.yml \
  -f docker-compose.prod.override.yml \
  up -d db

docker compose --env-file .env.prod \
  -f docker-compose.prod.yml \
  -f docker-compose.prod.override.yml \
  run --rm backend alembic upgrade head

docker compose --env-file .env.prod \
  -f docker-compose.prod.yml \
  -f docker-compose.prod.override.yml \
  up -d
```

En un primer despliegue desde cero no hay backup previo util. Antes de futuras
migraciones, el backup sera obligatorio.

## 9. Backup y restauracion

La base debe estar arrancada antes de hacer backup:

```bash
docker compose --env-file .env.prod -f docker-compose.prod.yml up -d db
docker compose --env-file .env.prod -f docker-compose.prod.yml ps
mkdir -p ~/backups/skillmatch
docker compose --env-file .env.prod -f docker-compose.prod.yml exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB"' > ~/backups/skillmatch/skillmatch_$(date +%Y%m%d_%H%M%S).sql
```

Restauracion orientativa:

```bash
cat ~/backups/skillmatch/backup_a_restaurar.sql | docker compose --env-file .env.prod -f docker-compose.prod.yml exec -T db sh -c 'psql -U "$POSTGRES_USER" "$POSTGRES_DB"'
```

Si usas override local, incluye tambien `-f docker-compose.prod.override.yml`
en ambos comandos.

Advertencias:

- No restaures sobre una base con datos sin confirmarlo expresamente.
- Prueba la restauracion en un entorno de prueba antes de depender de ella.
- No guardes backups en Git.
- Los backups contienen datos personales, CVs, emails, textos extraidos y datos
  derivados.
- En un primer despliegue desde cero no hay backup previo util.
- Antes de futuras migraciones, el backup sera obligatorio.

## 10. Smoke tests manuales

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

Comandos utiles:

```bash
docker compose --env-file .env.prod -f docker-compose.prod.yml ps
docker compose --env-file .env.prod -f docker-compose.prod.yml logs -f frontend
docker compose --env-file .env.prod -f docker-compose.prod.yml logs -f backend
docker compose --env-file .env.prod -f docker-compose.prod.yml logs -f email-worker
```

## 11. Rollback basico

Si algo falla:

1. No abras la aplicacion a usuarios.
2. Guarda logs relevantes.
3. Para servicios:

```bash
docker compose --env-file .env.prod -f docker-compose.prod.yml down
```

4. Si hubo migracion y necesitas volver atras, restaura un backup validado en
   un entorno controlado antes de hacerlo en el servidor real.
5. Si solo fallo la imagen, vuelve a la version anterior del repo o de la imagen
   y reconstruye.
6. No ejecutes `down -v` salvo que hayas confirmado que puedes borrar volumenes
   y datos.

## 12. Criterios para pasar a produccion cerrada

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
