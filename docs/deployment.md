# Despliegue de SkillMatch AI

Este documento describe la configuracion Docker de produccion inicial. No incluye
HTTPS real, dominio definitivo ni operacion completa de infraestructura.

## Desarrollo frente a produccion

`docker-compose.yml` sigue siendo el entorno de desarrollo:

- Monta codigo fuente con bind mounts.
- Publica PostgreSQL en `5432`.
- Ejecuta Angular con `ng serve`.
- Puede ejecutar migraciones automaticamente en el backend de desarrollo.

`docker-compose.prod.yml` es el entorno productivo:

- No monta el codigo fuente.
- Solo publica Nginx/frontend en `80:80`.
- PostgreSQL no publica puerto al host.
- Backend y `email-worker` son servicios separados.
- Angular se sirve como build estatico desde Nginx.
- Las migraciones se ejecutan manualmente.
- Swagger/OpenAPI queda deshabilitado en `ENVIRONMENT=production`.

## Crear `.env.prod`

1. Copia el ejemplo:

```bash
cp .env.prod.example .env.prod
```

2. Sustituye todos los placeholders antes de arrancar. No dejes valores como
`REPLACE_WITH_*`, `change_me` o `placeholder`: la aplicacion los rechaza en
produccion.

3. No subas `.env.prod` al repositorio.

Variables obligatorias principales:

- `ENVIRONMENT=production`
- `POSTGRES_DB`
- `POSTGRES_USER`
- `POSTGRES_PASSWORD`
- `DATABASE_URL`
- `SECRET_KEY`
- `FRONTEND_URL`
- `BACKEND_CORS_ORIGINS`
- `COOKIE_SECURE=true`
- `COOKIE_SAMESITE=lax`
- `EMAIL_PROVIDER=brevo`
- `BREVO_API_KEY`
- `EMAIL_FROM`
- `EMAIL_PAYLOAD_ENCRYPTION_KEY`
- `EMAIL_WORKER_POLL_SECONDS`
- `EMAIL_WORKER_BATCH_SIZE`
- `EMAIL_WORKER_STALE_MINUTES`
- `EMAIL_MAX_ATTEMPTS`
- `MAX_UPLOAD_SIZE_MB`
- `RESUME_MAX_PAGES`
- `RESUME_MIN_TEXT_CHARS`
- `PUBLIC_DEMO_RATE_LIMIT_PER_HOUR`
- `PUBLIC_DEMO_MAX_PAGES`
- `PUBLIC_DEMO_MIN_TEXT_CHARS`
- `JOB_SEARCH_RATE_LIMIT_PER_HOUR`
- `JOB_SEARCH_STALE_MINUTES`

Genera una clave Fernet para `EMAIL_PAYLOAD_ENCRYPTION_KEY` con:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

## Validaciones obligatorias de produccion

Con `ENVIRONMENT=production`, el backend rechaza configuraciones inseguras:

- `SECRET_KEY` debil, por defecto o placeholder.
- `DATABASE_URL` de ejemplo, con placeholders o sin PostgreSQL.
- `FRONTEND_URL` vacio, HTTP o local.
- `BACKEND_CORS_ORIGINS` con `*`, HTTP, localhost o sin incluir `FRONTEND_URL`.
- `COOKIE_SECURE=false`.
- `COOKIE_SAMESITE` distinto de `lax`.
- `EMAIL_PROVIDER` distinto de `brevo`.
- `BREVO_API_KEY` vacia o placeholder.
- `EMAIL_FROM` vacio, invalido o con dominio `example.com`.
- `EMAIL_PAYLOAD_ENCRYPTION_KEY` ausente, invalida, por defecto o placeholder.

## Brevo y correo real

En produccion se usa `EMAIL_PROVIDER=brevo`. `console` y `fake` quedan solo para
desarrollo y tests.

Pasos operativos:

1. Crear una API key SMTP/API en Brevo.
2. Configurar `BREVO_API_KEY` en `.env.prod`.
3. Configurar `EMAIL_FROM` con un remitente verificado, por ejemplo:
   `SkillMatch AI <noreply@TU_DOMINIO_VERIFICADO>`.
4. Verificar el dominio o remitente en Brevo.
5. Configurar SPF, DKIM y DMARC en DNS. Esto queda como requisito operativo
   pendiente antes de enviar correo real a usuarios.

Los endpoints de registro, reenvio de verificacion y recuperacion de contrasena
no llaman a Brevo directamente. Crean filas `pending` en `email_outbox`; el
servicio `email-worker` procesa la cola y envia con Brevo.

Para ver logs del worker:

```bash
docker compose --env-file .env.prod -f docker-compose.prod.yml logs -f email-worker
```

Para probar verificacion de email:

1. Arranca produccion con `.env.prod`.
2. Registra un usuario.
3. Comprueba logs de `email-worker`.
4. Verifica que llega el correo y que el enlace usa `FRONTEND_URL`.
5. Abre el enlace y confirma que la cuenta pasa a `active`.

Para probar recuperacion de contrasena:

1. Solicita reset desde `/forgot-password`.
2. Comprueba logs de `email-worker`.
3. Verifica que llega el correo y que el enlace usa `FRONTEND_URL`.
4. Cambia la contrasena desde `/reset-password?token=...`.

Si el envio falla temporalmente, el worker reintenta segun el calendario de
outbox. Si falla de forma terminal, marca la fila segun el estado previsto y no
debe registrar tokens ni enlaces completos.

## Swagger y OpenAPI

En desarrollo siguen disponibles:

- `/docs`
- `/redoc`
- `/api/v1/openapi.json`

En produccion quedan deshabilitados:

- `/docs`
- `/redoc`
- `/api/v1/openapi.json`

Esto evita exponer documentacion automatica de API en una instalacion publica.

## Build productivo

```bash
docker compose --env-file .env.prod -f docker-compose.prod.yml build
```

El frontend usa multi-stage build:

- Node 20 ejecuta `npm ci`.
- Se ejecuta `npm run build`.
- La imagen final usa Nginx.
- `node_modules` no queda en la imagen final.

El backend usa `backend/Dockerfile.prod`:

- Instala dependencias sin extras de desarrollo.
- Copia `app`, `alembic` y `data`.
- Ejecuta como usuario no root.
- No ejecuta migraciones automaticamente.

## Migraciones

Antes de migrar, haz backup de la base de datos.

Orden recomendado:

1. Backup.
2. Build.
3. Migracion.
4. Arranque.
5. Healthcheck.

Comando de migracion:

```bash
docker compose --env-file .env.prod -f docker-compose.prod.yml run --rm backend alembic upgrade head
```

## Arranque

```bash
docker compose --env-file .env.prod -f docker-compose.prod.yml up -d
```

Servicios:

- `db`: PostgreSQL con pgvector.
- `backend`: FastAPI interno, sin puerto publicado al host.
- `email-worker`: envio de email desde `email_outbox`.
- `frontend`: Nginx publico en `80:80`.

## Healthchecks

Comprobar estado:

```bash
docker compose --env-file .env.prod -f docker-compose.prod.yml ps
```

Comprobar API desde el host:

```bash
curl http://localhost/api/v1/health
```

El proxy Nginx mantiene `/api/v1/...` sin duplicar `/api`.

## Logs

```bash
docker compose --env-file .env.prod -f docker-compose.prod.yml logs -f frontend
docker compose --env-file .env.prod -f docker-compose.prod.yml logs -f backend
docker compose --env-file .env.prod -f docker-compose.prod.yml logs -f email-worker
docker compose --env-file .env.prod -f docker-compose.prod.yml logs -f db
```

## Parada

```bash
docker compose --env-file .env.prod -f docker-compose.prod.yml down
```

Para parar sin borrar volumenes, no uses `-v`.

## Backup minimo antes de migrar

Ejemplo orientativo:

```bash
docker compose --env-file .env.prod -f docker-compose.prod.yml exec db pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB" > backup.sql
```

Valida el comando en el servidor real antes de confiar en el como estrategia de
backup.

## Validaciones antes de desplegar

Backend:

```bash
docker compose exec backend pytest -q
docker compose exec backend ruff check app tests
docker compose exec backend python -m pip check
docker compose exec backend alembic check
```

Frontend:

```bash
cd frontend
npm run test:ci
npm run build
npm audit --omit=dev
cd ..
```

Docker:

```bash
docker compose config --quiet
docker compose -f docker-compose.prod.yml config --quiet
docker compose -f docker-compose.prod.yml build
```

## Limitaciones pendientes

- HTTPS y certificados reales.
- Dominio definitivo.
- Backups automatizados y restauracion probada.
- Monitorizacion y alertas.
- Cola durable para tareas de busqueda y procesamiento.
- SPF, DKIM y DMARC configurados y verificados en DNS.
- CSP mas estricta tras validar todos los assets.
- Hardening completo de infraestructura.
- Limites de recursos por contenedor ajustados a la maquina real.
- Optimizacion de imagen backend: las dependencias de IA/ML actuales hacen que
  el build descargue paquetes grandes; queda pendiente evaluar imagen CPU-only o
  separacion de workers ML.
