# Despliegue de SkillMatch AI

Este documento describe la configuracion Docker de produccion inicial. No incluye
HTTPS real, dominio definitivo ni operacion completa de infraestructura.

Para el primer despliegue controlado/staging en VPS con Nginx host, Certbot,
HTTPS y UFW, seguir `docs/staging-runbook.md`.

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

Las imagenes de desarrollo y produccion usan tags separados para evitar que un
build productivo sustituya la imagen usada por el entorno local:

- Desarrollo backend: `skillmatch-ai-backend:dev`.
- Produccion backend y `email-worker`: `skillmatch-ai-backend:prod`.
- Produccion frontend: `skillmatch-ai-frontend:prod`.

Si despues de cambiar tags Docker mantiene un contenedor antiguo, recrea el
backend local de forma controlada:

```bash
docker compose up -d --force-recreate backend
```

Construir produccion con `docker compose -f docker-compose.prod.yml build` no
debe afectar a `skillmatch-ai-backend:dev`.

## Dominio y HTTPS

Opcion recomendada para este VPS: usar Nginx instalado en el host como reverse
proxy externo para gestionar HTTPS con Certbot.

Flujo recomendado:

```text
Internet -> reverse proxy del host con HTTPS -> contenedor frontend/Nginx HTTP -> backend interno
```

Ventajas:

- Los certificados quedan fuera del repositorio y fuera de la imagen Docker.
- Puedes renovar certificados en el host con la herramienta que prefieras.
- El contenedor frontend sigue siendo simple y sirve HTTP interno.
- Backend, PostgreSQL y `email-worker` siguen sin publicarse al exterior.

No guardes certificados, claves privadas ni configuraciones con secretos en Git.

Alternativa avanzada: gestionar TLS dentro del contenedor frontend. En ese caso,
monta certificados como volumen externo de solo lectura y no los copies a la
imagen ni al repositorio. Esta opcion requiere ajustar `frontend/nginx.prod.conf`
para escuchar en `443` y queda fuera de la configuracion por defecto.

### Puertos con reverse proxy externo

La configuracion inicial publica:

```yaml
ports:
  - "80:80"
```

Si delante hay un reverse proxy externo en el host, puedes limitar el puerto al
loopback del servidor:

```yaml
ports:
  - "127.0.0.1:8080:80"
```

Con esa variante, el proxy externo deberia apuntar a `http://127.0.0.1:8080`.
No cambies este mapeo sin validar primero el proxy y el healthcheck.

Para un VPS con datos persistentes fuera del repo, usa como base
`docker-compose.prod.override.example.yml` y copialo en el servidor como
`docker-compose.prod.override.yml`. El override real esta ignorado por Git y
puede montar:

- `/srv/data/skillmatch-ai/postgres` en `/var/lib/postgresql/data`.
- `/srv/data/skillmatch-ai/uploads` en `/app/storage/resumes`.
- `127.0.0.1:8080:80` para frontend.
- `127.0.0.1:8001:8000` para backend solo si Nginx host necesita proxyear
  directamente a FastAPI.

PostgreSQL no debe publicar `5432` al host.

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

Para dominio real, estos valores deben coincidir:

```env
FRONTEND_URL=https://DOMINIO_REAL
BACKEND_CORS_ORIGINS=["https://DOMINIO_REAL"]
COOKIE_SECURE=true
COOKIE_SAMESITE=lax
```

Si el frontend y la API se sirven bajo el mismo dominio, el navegador llamara a
`/api/...` y Nginx lo enviara al backend interno. No publiques el backend
directamente salvo que cambies el diseno de despliegue y revises CORS/Origin.

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

Checklist DNS y Brevo:

- Crear un `A record` del dominio hacia la IP publica del VPS.
- Activar HTTPS/certificado en el reverse proxy externo.
- Configurar `FRONTEND_URL=https://DOMINIO_REAL`.
- Configurar `BACKEND_CORS_ORIGINS=["https://DOMINIO_REAL"]`.
- Guardar `BREVO_API_KEY` solo en `.env.prod` o en el sistema de secretos real.
- Verificar remitente o dominio en Brevo.
- Configurar SPF segun las instrucciones de Brevo.
- Configurar DKIM segun las instrucciones de Brevo.
- Configurar DMARC, al menos con politica inicial de monitorizacion.
- Probar registro de usuario.
- Probar verificacion de email.
- Probar recuperacion de contrasena.

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

## Cabeceras de seguridad en Nginx

`frontend/nginx.prod.conf` aplica cabeceras basicas:

- `X-Content-Type-Options: nosniff`
- `Referrer-Policy: strict-origin-when-cross-origin`
- `X-Frame-Options: DENY`
- `Permissions-Policy` deshabilitando camara, microfono, geolocalizacion y pagos.
- CSP conservadora compatible con Angular y llamadas relativas a `/api/...`.

HSTS no esta activado por defecto. Activalo solo cuando:

- el dominio real funcione con HTTPS;
- el certificado sea valido y renovable;
- hayas probado acceso real por HTTPS;
- no necesites servir la aplicacion por HTTP.

Cabecera orientativa para activar despues:

```nginx
add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
```

La CSP actual prioriza no romper la SPA. Un endurecimiento mas estricto debe
probarse con el dominio real, assets definitivos y cualquier proveedor externo
que se anada en el futuro.

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

El unico punto de entrada externo debe ser `frontend` o el reverse proxy externo
del host. PostgreSQL, backend y `email-worker` no deben publicar puertos al
exterior.

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

## Operacion habitual

Ver contenedores:

```bash
docker compose --env-file .env.prod -f docker-compose.prod.yml ps
```

Ejecutar migraciones manuales:

```bash
docker compose --env-file .env.prod -f docker-compose.prod.yml run --rm backend alembic upgrade head
```

Ejecutar limpieza de datos temporales en modo simulacion:

```bash
docker compose --env-file .env.prod -f docker-compose.prod.yml run --rm backend python -m app.commands.cleanup --dry-run
```

Ejecutar limpieza real despues de revisar el `--dry-run`:

```bash
docker compose --env-file .env.prod -f docker-compose.prod.yml run --rm backend python -m app.commands.cleanup
```

Comprobar healthcheck HTTP:

```bash
curl http://localhost/api/v1/health
```

Si usas dominio real con HTTPS:

```bash
curl https://DOMINIO_REAL/api/v1/health
```

## Parada

```bash
docker compose --env-file .env.prod -f docker-compose.prod.yml down
```

Para parar sin borrar volumenes, no uses `-v`.

## Backup y restauracion minima

Haz backup antes de cualquier migracion o despliegue que pueda cambiar datos.
Guarda el backup fuera del contenedor y, preferiblemente, fuera del VPS.

Backup con `pg_dump`:

```bash
mkdir -p /srv/backups/skillmatch-ai/postgres

docker compose --env-file .env.prod \
  -f docker-compose.prod.yml \
  -f docker-compose.prod.override.yml \
  exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB"' \
  > /srv/backups/skillmatch-ai/postgres/skillmatch_$(date +%Y%m%d_%H%M%S).sql
```

Restauracion orientativa en una base vacia o entorno de prueba:

```bash
cat /srv/backups/skillmatch-ai/postgres/backup_a_restaurar.sql | docker compose --env-file .env.prod \
  -f docker-compose.prod.yml \
  -f docker-compose.prod.override.yml \
  exec -T db sh -c 'psql -U "$POSTGRES_USER" "$POSTGRES_DB"'
```

Advertencias:

- Prueba la restauracion antes de abrir la aplicacion a usuarios reales.
- No guardes backups en Git.
- Protege los backups porque pueden contener CVs, emails y datos personales.
- Define retencion, cifrado y ubicacion externa en una fase operativa posterior.

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
