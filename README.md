# SkillMatch AI

Aplicacion web que analiza un CV, construye un perfil profesional y ordena ofertas
tecnologicas por compatibilidad explicable.

![Landing de SkillMatch AI](landing-desktop.png)

## Que Problema Resuelve

Buscar empleo obliga a comparar manualmente el contenido de un CV con descripciones
de ofertas heterogeneas. Los portales suelen ordenar por palabras clave o criterios
opacos y no explican por que una oferta encaja.

SkillMatch AI automatiza ese trabajo:

1. Extrae texto de un CV PDF validado de forma defensiva.
2. Detecta skills, experiencia, idiomas, formacion y tipo de perfil.
3. Busca ofertas relacionadas con ese perfil.
4. Calcula una compatibilidad combinando reglas y similitud semantica.
5. Explica las coincidencias y las skills que faltan.
6. Permite guardar, descartar o marcar ofertas como postuladas.

El objetivo no es decidir por la persona candidata, sino reducir el tiempo de
revision y hacer visible el criterio usado en el ranking.

## Que Datos Usa

El proyecto trabaja con cuatro grupos de datos:

- **CV del usuario:** documento PDF subido de forma privada. No se incluyen CV
  reales en el repositorio.
- **Diccionario de skills:** 90 habilidades versionadas en
  `data/skills/skills.es.json`, con categorias y aliases en espanol e ingles.
- **Taxonomia local:** 13 categorias tecnicas y aliases canonicos en
  `data/skills/skill_taxonomy.es.json`.
- **Ofertas de empleo:** Tecnoempleo como fuente activa por defecto e InfoJobs
  mediante su API oficial cuando existen credenciales. Se conserva fuente, URL,
  empresa, ubicacion, modalidad, requisitos y metadatos disponibles.

Tambien existe una oferta semilla en `data/sample_jobs/jobs.sample.json` para
pruebas controladas. El feedback del usuario se guarda como interacciones, pero
todavia no se usa para entrenar modelos.

## Decisiones Tecnicas

### Matching explicable

El score actual es:

```text
compatibilidad = 65% coincidencia de skills + 35% similitud semantica
```

- La parte de reglas compara skills normalizadas del perfil y de la oferta.
- La parte semantica usa
  `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`.
- Los embeddings de 384 dimensiones se almacenan con pgvector.
- Cada resultado guarda ambos scores, explicacion y version del algoritmo
  (`hybrid-rules-semantic-v1`).

Se eligio un enfoque hibrido porque un embedding aislado aporta cobertura semantica,
pero las reglas permiten explicar coincidencias concretas.

### Procesamiento de CV

- PyMuPDF para PDF, con validacion de extension, MIME, cabecera real, parseo,
  limite de paginas, limite de tamano y minimo de texto extraible.
- Normalizacion de texto antes de extraer informacion.
- Diccionario y taxonomia local como fuente principal de skills.
- Patrones conservadores para terminos tecnicos no registrados.
- GLiNER opcional; el MVP no depende de entrenar un modelo propio.
- Solo un CV permanece activo por usuario para evitar rankings ambiguos.
- La pantalla de CV muestra un aviso informativo antes de subir el archivo; el
  usuario puede eliminarlo junto con su perfil y resultados derivados.

### Seguridad

- Sesiones opacas almacenadas en PostgreSQL.
- Cookie HttpOnly; no se guardan tokens de sesion en `localStorage`.
- Contrasenas con Argon2id y migracion automatica desde bcrypt.
- Registro con respuesta generica para reducir enumeracion de emails.
- Verificacion de correo mediante token aleatorio de 24 horas, de un solo uso y
  almacenado solo como hash.
- Usuarios pendientes pueden autenticarse, pero no acceder a CV, ofertas o feedback.
- El token necesario para construir el correo se cifra con Fernet dentro de
  `email_outbox`; nunca se persiste en texto plano.
- Registro y reenvio solo encolan el correo. Un worker separado lo entrega mediante
  consola en desarrollo o Brevo API en produccion.
- El worker recupera entregas abandonadas, cancela tokens invalidados y reintenta a
  los 1, 5, 15, 60 y 240 minutos.
- Las escrituras autenticadas validan `Origin` contra `FRONTEND_URL` y los origenes
  CORS permitidos.
- Login, registro, reenvio y recuperacion usan limites persistentes en PostgreSQL.
  Las claves son HMAC-SHA256 y no guardan emails ni IPs en claro.
- Un comando de mantenimiento elimina sesiones, tokens, correos finalizados,
  buckets antiguos y recupera estados abandonados con retenciones configurables.
- En produccion Brevo es el proveedor obligatorio de correo; Console y Fake quedan
  para desarrollo y tests.
- Swagger/OpenAPI permanece disponible en desarrollo y se deshabilita en
  produccion.

### Arquitectura

```text
Angular 20
    |
    | HTTP + cookie HttpOnly
    v
FastAPI + SQLAlchemy + servicios NLP/matching
    |
    +----------> PostgreSQL 16 + pgvector + email_outbox
                                      |
                                      v
                              email-worker -> Console/Brevo
```

El backend separa autenticacion, procesamiento de CV, importacion de ofertas,
embeddings y matching. Alembic versiona el esquema y Docker Compose levanta el
entorno local.

## Conclusiones

- La combinacion de reglas y embeddings produce un ranking interpretable sin
  entrenar un modelo desde cero.
- Normalizar skills antes de comparar es tan importante como la similitud semantica:
  reduce diferencias de aliases y tecnologias equivalentes.
- Mantener el CV activo, la version del algoritmo y los resultados persistidos hace
  el comportamiento reproducible.
- Las fuentes externas condicionan la calidad final. Por eso la aplicacion conserva
  atribucion y URL original, y trata InfoJobs como integracion opcional.
- El feedback ya queda estructurado para una fase supervisada futura, pero aun no hay
  evidencia suficiente para afirmar mejora predictiva.
- Antes de una operacion a mayor escala faltan observabilidad, backups probados,
  politica completa para CV/cuentas y evaluacion con pares CV-oferta etiquetados.

## Funcionalidades Actuales

- Registro, login, logout y restauracion de sesion.
- Verificacion y reenvio de correo.
- Recuperacion de contrasena por enlace de un solo uso.
- Cambio de contrasena con revocacion de las demas sesiones.
- Subida y procesamiento de CV.
- Perfil profesional estructurado.
- Busqueda asincrona de ofertas por perfil.
- Recomendaciones paginadas y explicadas.
- Guardado, descarte y postulacion de ofertas.
- Eliminacion de CV con borrado de archivo y datos derivados, conservando
  interacciones desvinculadas.
- Perfil y ajustes de cuenta.
- Guards Angular y dependencias FastAPI para usuarios verificados.
- Configuracion Docker separada para desarrollo y produccion.

## Stack

- Angular 20, TypeScript y SCSS.
- FastAPI, Python 3.12, SQLAlchemy, Alembic y Pydantic.
- PostgreSQL 16 y pgvector.
- sentence-transformers, spaCy y PyMuPDF.
- Docker Compose y Nginx.

## Arranque Local

Requisitos: Docker Desktop y Docker Compose.

```bash
cp .env.example .env
docker compose up --build -d
```

En PowerShell:

```powershell
Copy-Item .env.example .env
docker compose up --build -d
```

Servicios:

- Frontend: http://localhost:4200
- Backend: http://localhost:8000
- Swagger/OpenAPI: http://localhost:8000/docs
- Healthcheck: http://localhost:8000/api/v1/health

En desarrollo, el enlace de verificacion aparece en:

```bash
docker compose logs email-worker
```

Migraciones y estado de servicios:

```bash
docker compose exec backend alembic upgrade head
docker compose ps
docker compose logs backend
docker compose logs email-worker
```

El backend aplica las migraciones al arrancar. El comando explicito resulta util
para despliegues controlados.

## Configuracion De Produccion

Para produccion, genere secretos propios y configure al menos:

```env
ENVIRONMENT=production
DATABASE_URL=postgresql+psycopg://usuario:password-fuerte@db:5432/skillmatch
SECRET_KEY=un-secreto-aleatorio-de-al-menos-32-caracteres
FRONTEND_URL=https://REPLACE_WITH_FRONTEND_DOMAIN
BACKEND_CORS_ORIGINS=["https://REPLACE_WITH_FRONTEND_DOMAIN"]
COOKIE_SECURE=true
COOKIE_SAMESITE=lax
TRUST_PROXY_HEADERS=false
EMAIL_PROVIDER=brevo
BREVO_API_KEY=...
EMAIL_FROM=SkillMatch AI <noreply@REPLACE_WITH_VERIFIED_DOMAIN>
EMAIL_PAYLOAD_ENCRYPTION_KEY=...
EMAIL_MAX_ATTEMPTS=6
PASSWORD_RESET_TTL_MINUTES=60
PASSWORD_RESET_MAX_REQUESTS_PER_HOUR=5
```

La aplicacion rechaza el arranque productivo con credenciales predeterminadas,
placeholders sin sustituir, HTTP/localhost en CORS, cookie insegura o proveedor de
correo distinto de Brevo. `TRUST_PROXY_HEADERS` solo debe activarse si FastAPI no
es accesible directamente y el proxy controlado sobrescribe `X-Forwarded-For`.

Variables operativas principales:

| Variable | Uso |
|---|---|
| `ENVIRONMENT` | `development`, `test` o `production` |
| `DATABASE_URL` | PostgreSQL; credenciales propias obligatorias en produccion |
| `SECRET_KEY` | Firma HMAC de buckets; minimo 32 caracteres en produccion |
| `FRONTEND_URL` | Origen canonico del frontend y base de enlaces |
| `BACKEND_CORS_ORIGINS` | Lista JSON de origenes permitidos |
| `SESSION_DAYS` | Duracion de la cookie y sesion opaca |
| `COOKIE_SECURE` / `COOKIE_SAMESITE` | `true` y `lax` en produccion |
| `EMAIL_PROVIDER` | `console` local, `fake` tests o `brevo` produccion |
| `BREVO_API_KEY` / `EMAIL_FROM` | Credenciales y remitente verificado |
| `EMAIL_PAYLOAD_ENCRYPTION_KEY` | Clave Fernet estable para el outbox |
| `EMAIL_WORKER_POLL_SECONDS` | Espera del worker cuando no hay trabajo |
| `EMAIL_WORKER_BATCH_SIZE` | Filas reclamadas por iteracion |
| `EMAIL_WORKER_STALE_MINUTES` | Umbral para recuperar entregas abandonadas |
| `EMAIL_MAX_ATTEMPTS` | Hasta 6: intento inicial y cinco reintentos |
| `EMAIL_HTTP_TIMEOUT_SECONDS` | Timeout de la llamada a Brevo |
| `CLEANUP_*_RETENTION_DAYS` | Retenciones de sesiones, tokens y outbox |

Los limites se pueden ajustar con las variables `*_RATE_LIMIT_*` de
`.env.example`. No existen `BACKEND_URL` ni `CSRF_SECRET`: la API usa rutas
relativas y protege escrituras con cookie validando `Origin`.

Puede generar la clave con:

```bash
docker compose run --rm backend python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

No cambie la clave mientras haya correos pendientes: esos payloads dejarian de poder
descifrarse. En produccion no se registran enlaces completos ni tokens.

En Brevo debe verificar el dominio o remitente configurado en `EMAIL_FROM`. Publique
los registros SPF y DKIM que muestre el panel de Brevo y espere a que aparezcan como
validados antes de enviar correo real. DMARC es recomendable una vez comprobada la
entrega.

## Limites Y Limpieza

Valores predeterminados:

- login: 10 intentos por IP/email cada 15 minutos;
- registro: 5 solicitudes por IP y hora;
- reenvio: cooldown de 60 segundos y 5 solicitudes por usuario/hora;
- recuperar contrasena: 5 por email y 20 por IP/hora;
- restablecer: 10 por IP/hora;
- cambiar contrasena: 5 por usuario/hora.

Registro y recuperacion mantienen siempre su respuesta generica. Los demas limites
devuelven `429` con `Retry-After`.

Revise primero los contadores:

```bash
docker compose exec backend python -m app.commands.cleanup --dry-run
```

Ejecute la limpieza:

```bash
docker compose exec backend python -m app.commands.cleanup
```

Por defecto conserva 30 dias de sesiones inactivas, 7 dias de tokens usados o
caducados y 30 dias de correos finalizados. Se puede sobrescribir con
`--session-retention-days`, `--token-retention-days` y
`--outbox-retention-days`. En produccion debe programarse periodicamente, por
ejemplo una vez al dia desde el scheduler de la plataforma.

InfoJobs es opcional. Para activarlo, configure
`INFOJOBS_CLIENT_ID` y `INFOJOBS_CLIENT_SECRET` en `.env`.

## Pruebas

```bash
docker compose exec backend pytest -q
docker compose exec backend ruff check app tests

cd frontend
npm install
npm run test:ci
npm run build
```

Estado validado el 23 de junio de 2026:

- 178 pruebas backend superadas.
- 52 pruebas Angular superadas.
- Build Angular y lint backend correctos.
- `npm audit --omit=dev` sin vulnerabilidades de produccion.
- Alembic alineado con los modelos.

## Despliegue en producción

SkillMatch AI esta desplegado en un VPS Ubuntu de Hostinger mediante Docker
Compose. Nginx actua como reverse proxy y termina HTTPS; PostgreSQL 16 con
pgvector se ejecuta en una red privada de Docker sin publicar su puerto.

- URL publica: [https://skillmatch.jabejarano.tech](https://skillmatch.jabejarano.tech).
- Despliegue real en VPS: [docs/deployment-vps.md](docs/deployment-vps.md).
- Guia general de despliegue: [docs/deployment.md](docs/deployment.md).
- Runbook de staging: [docs/staging-runbook.md](docs/staging-runbook.md).
- Borrador tecnico de privacidad: [docs/privacy.md](docs/privacy.md).

Los archivos `.env.prod`, los overrides locales, los backups y los dumps SQL no
deben subirse al repositorio: contienen configuracion del servidor o pueden
incluir datos personales.

## Estructura

```text
backend/       API, modelos, migraciones y servicios
frontend/      Aplicacion Angular
data/          Diccionario, taxonomia y datos semilla
docs/          Documentacion tecnica
docker/        PostgreSQL y Nginx
storage/       CVs locales, excluidos de Git
tests/         Pruebas backend
```

## Documentacion

- [Estado actual](docs/estado-actual.md)
- [Arquitectura](docs/arquitectura.md)
- [API](docs/api.md)
- [Modelo de datos](docs/modelo-datos.md)
- [Fases](docs/fases.md)
