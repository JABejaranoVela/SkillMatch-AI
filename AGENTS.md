# AGENTS.md - SkillMatch AI

## Proyecto

SkillMatch AI es una aplicación Angular + FastAPI para analizar CVs en PDF, generar perfiles profesionales y recomendar ofertas compatibles.

Stack principal:
- Frontend: Angular 20.
- Backend: FastAPI + SQLAlchemy + Alembic.
- Base de datos: PostgreSQL 16 + pgvector.
- Infraestructura: Docker Compose para desarrollo y producción.
- Producción: Nginx como frontend/proxy.
- Email: `email_outbox` + `email-worker`; Brevo para staging/producción.
- Autenticación: sesiones opacas con cookie HttpOnly.
- CVs: solo PDF. DOCX debe rechazarse.

## Reglas generales

- Antes de modificar archivos, ejecutar `git status --short`.
- Mantener cambios pequeños, enfocados y reversibles.
- No tocar lógica funcional salvo petición explícita.
- No introducir secretos, API keys, tokens, hashes, contraseñas ni payloads cifrados en código, tests o documentación.
- No versionar `.env`, `.env.prod`, backups, dumps, CVs reales ni logs.
- No imprimir secretos ni contenido completo de `.env`.
- No usar datos personales reales en tests o documentación.
- No tocar migraciones salvo petición explícita.
- No tocar Docker de producción salvo petición explícita.
- No romper el entorno de desarrollo.
- Si hay duda antes de borrar, migrar o simplificar algo, preguntar.

## Code Review Rules

- **Autorización de recursos privados.** Señala cualquier cambio que permita leer,
  modificar, procesar o borrar un CV, un perfil o un resultado privado sin
  comprobar en el backend que pertenece al usuario autenticado. La comprobación
  debe cubrir también los accesos indirectos y las rutas nuevas. En escrituras
  autenticadas por cookie, conserva la comprobación del origen permitido.

- **Coherencia entre PostgreSQL y los PDF.** Señala los cambios que puedan
  eliminar un PDF referenciado por una fila confirmada o dejarlo huérfano tras
  un fallo confirmado del alta. Compensa el fallo confirmado y conserva el
  archivo cuando el resultado del commit sea indeterminado, hasta que una
  reconciliación pueda verificar su estado. Para cambios en esta frontera,
  pide una regresión que distinga ambos resultados.

- **Confianza y consistencia de las releases.** Señala cualquier ruta desde
  código, entradas o cachés de una PR hacia publicación o producción que
  eluda la validación del SHA de release o el aislamiento de caché. La
  validación reutilizada debe ejecutar el SHA autorizado con `cache-mode: none`
  y los builds privilegiados deben mantenerse fuera de la caché GHA. Antes de
  aceptar un reintento como exitoso, exige que la release completada, el
  checkout limpio, la configuración persistida y los digests efectivos
  coincidan, y que se haya resuelto cualquier despliegue pendiente.

## Convenciones actuales

- Angular actual: 20.
- CV aceptado: PDF.
- DOCX: rechazado.
- Las rutas protegidas dependen de sesión HttpOnly, no de JWT en localStorage.
- Swagger/OpenAPI está disponible en desarrollo y deshabilitado en producción.
- El backend de desarrollo usa la imagen `skillmatch-ai-backend:dev`.
- Producción usa:
  - `skillmatch-ai-backend:prod`
  - `skillmatch-ai-frontend:prod`
- El envío de email no lo hacen directamente los endpoints: se encola en `email_outbox` y lo procesa `email-worker`.
- No cambiar `EMAIL_PAYLOAD_ENCRYPTION_KEY` si hay emails pendientes en `email_outbox`.

## Validaciones

### Backend

Ejecuta desde la raíz con Docker local en modo contenedores Linux, Docker Compose v2 y las
imágenes locales `skillmatch-ai-backend:dev` y `pgvector/pgvector:pg16`. Si faltan, prepara
la imagen backend con `docker build -t skillmatch-ai-backend:dev ./backend` y obtén PostgreSQL
con `docker pull pgvector/pgvector:pg16`.

```bash
docker compose -p skillmatch-backend-test -f docker-compose.test.yml up --force-recreate --exit-code-from backend
```

El comando verifica la identidad y la marca de la base desechable, aplica las migraciones,
ejecuta `backend/tests` y `tests`, y comprueba Ruff, las dependencias Python y Alembic. Devuelve
el código de salida del backend de pruebas. PostgreSQL y los CV usan memoria temporal. Los
contenedores se comunican por una red privada del proyecto de pruebas.
Usa este nombre de proyecto para una sola ejecución a la vez.

Al terminar, incluso si falla una comprobación o interrumpes la ejecución, retira los
contenedores y la red de pruebas con este comando:

```bash
docker compose -p skillmatch-backend-test -f docker-compose.test.yml down
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

## Cuándo ejecutar validaciones

- Si se toca backend: ejecutar validaciones backend.
- Si se toca frontend: ejecutar validaciones frontend.
- Si se toca Docker, `.env.example`, `.env.prod.example` o despliegue: ejecutar validaciones Docker.
- Si solo se toca documentación: basta con `git status --short` y, si procede, validación de compose.

## Documentación de referencia

Consultar antes de asumir comportamiento:

- Estado actual: `docs/estado-actual.md`
- Arquitectura: `docs/arquitectura.md`
- API: `docs/api.md`
- Privacidad técnica: `docs/privacy.md`
- Despliegue: `docs/deployment.md`
- Staging: `docs/staging-runbook.md`

## Flujo de trabajo

Al finalizar una tarea, informar siempre:

1. Archivos modificados.
2. Qué se ha cambiado.
3. Validaciones ejecutadas.
4. Resultado de las validaciones.
5. Riesgos o pendientes.
6. Si no se ejecutó alguna validación, explicar por qué.
