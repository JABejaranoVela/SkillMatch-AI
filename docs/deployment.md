# Despliegue de SkillMatch AI

Este documento describe la configuración Docker de producción inicial. No incluye HTTPS real, dominio definitivo ni operación completa de infraestructura.

## Desarrollo frente a producción

`docker-compose.yml` sigue siendo el entorno de desarrollo:

- Monta código fuente con bind mounts.
- Publica PostgreSQL en `5432`.
- Ejecuta Angular con `ng serve`.
- Puede ejecutar migraciones automáticamente en el backend de desarrollo.

`docker-compose.prod.yml` es el entorno productivo:

- No monta el código fuente.
- Solo publica Nginx/frontend en `80:80`.
- PostgreSQL no publica puerto al host.
- Backend y `email-worker` son servicios separados.
- Angular se sirve como build estático desde Nginx.
- Las migraciones se ejecutan manualmente.

## Variables de producción

1. Copia el ejemplo:

```bash
cp .env.prod.example .env.prod
```

2. Rellena todos los secretos y dominios antes de arrancar.

Variables críticas:

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

Genera una clave Fernet para `EMAIL_PAYLOAD_ENCRYPTION_KEY` con:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

No subas `.env.prod` al repositorio.

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
- No ejecuta migraciones automáticamente.

## Migraciones

Antes de migrar, haz backup de la base de datos.

Orden recomendado:

1. Backup.
2. Build.
3. Migración.
4. Arranque.
5. Healthcheck.

Comando de migración:

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
- `email-worker`: envío de email desde `email_outbox`.
- `frontend`: Nginx público en `80:80`.

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

Para parar sin borrar volúmenes, no uses `-v`.

## Backup mínimo antes de migrar

Ejemplo orientativo:

```bash
docker compose --env-file .env.prod -f docker-compose.prod.yml exec db pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB" > backup.sql
```

Valida el comando en el servidor real antes de confiar en él como estrategia de backup.

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
- Backups automatizados y restauración probada.
- Monitorización y alertas.
- Cola durable para tareas de búsqueda y procesamiento.
- CSP más estricta tras validar todos los assets.
- Hardening completo de infraestructura.
- Límites de recursos por contenedor ajustados a la máquina real.
- Optimización de imagen backend: las dependencias de IA/ML actuales hacen que el build descargue paquetes grandes; queda pendiente evaluar imagen CPU-only o separación de workers ML.
