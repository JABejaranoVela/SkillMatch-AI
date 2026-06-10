# Arquitectura

## Vision General

SkillMatch AI usa una arquitectura web de tres capas:

```text
Angular 18
    |
    | REST + cookie HttpOnly
    v
FastAPI / SQLAlchemy / servicios de dominio
    |
    v
PostgreSQL 16 + pgvector
```

Docker Compose levanta base de datos, backend y frontend. Nginx sirve la aplicacion
compilada en la imagen de produccion y redirige `/api` a FastAPI.

## Frontend

La aplicacion Angular contiene:

- `core/`: interceptor de credenciales y guards.
- `features/auth/`: login, registro y verificacion de correo.
- `features/resumes/`: subida, procesamiento y perfil extraido.
- `features/jobs/`: busqueda y recomendaciones.
- `features/saved-jobs/`: ofertas guardadas/postuladas.
- `features/profile/` y `features/settings/`: cuenta.

`AuthService` restaura la sesion al arrancar. `verifiedGuard` exige usuario activo y
correo verificado en las rutas privadas.

## Backend

FastAPI organiza la API en:

- `api/deps.py`: sesion actual, usuario actual, usuario activo y usuario pendiente.
- `api/v1/endpoints/`: auth, resumes, jobs, feedback y health.
- `services/auth/`: sesiones, tokens de cuenta y correo.
- `services/cv_processing/`: almacenamiento, extraccion y perfil.
- `services/nlp/`: normalizacion, skills, taxonomia y NER.
- `services/jobs_import/`: Tecnoempleo, InfoJobs, importacion y upsert.
- `services/embeddings/`: generacion y similitud vectorial.
- `services/matching/`: reglas y score hibrido.

Las tareas de busqueda se ejecutan con `BackgroundTasks` y persisten su estado en
`job_search_tasks`.

## Flujo De Autenticacion

1. El registro crea un usuario `pending`.
2. Se crea un token aleatorio, se persiste su hash y se registra `email_outbox`.
3. En desarrollo, `ConsoleEmailService` escribe el enlace en logs.
4. Login crea una sesion opaca y una cookie HttpOnly.
5. La verificacion bloquea la fila del token, valida uso/caducidad y activa al usuario.
6. Backend y frontend impiden que un usuario pendiente use CV, ofertas o feedback.

## Flujo De CV

1. Se valida extension y tamano.
2. El archivo se guarda fuera del repositorio.
3. Se desactiva el CV anterior.
4. PyMuPDF/python-docx extrae el texto.
5. Se normaliza el contenido.
6. Se detectan skills y evidencias.
7. Se crea `professional_profiles` y su embedding.

## Flujo De Ofertas

1. El perfil genera terminos de busqueda.
2. Tecnoempleo se consulta por defecto.
3. InfoJobs se consulta si existen credenciales.
4. Las ofertas se normalizan y actualizan por `(source, external_id)`.
5. Se generan embeddings cuando son necesarios.
6. Se calculan y persisten resultados para el CV activo.

## Matching

```text
rules_score = skills coincidentes / skills detectadas en la oferta
semantic_score = similitud coseno entre embeddings
final_score = 0.65 * rules_score + 0.35 * semantic_score
```

La explicacion almacena coincidencias, ausencias, senales positivas, penalizaciones y
desglose de pesos. La version del algoritmo evita mezclar resultados incompatibles.

## Persistencia

- PostgreSQL es la fuente de verdad.
- pgvector almacena embeddings de perfil y oferta.
- Alembic versiona el esquema.
- El filesystem local almacena CVs; la base solo conserva metadatos y ruta interna.
- Los CV, secretos, logs y bases locales se excluyen mediante `.gitignore`.

## Limites Actuales

- `BackgroundTasks` no sustituye una cola distribuida.
- `ConsoleEmailService` no entrega correo real.
- Tecnoempleo depende de la estructura HTML del portal.
- No existe aun recuperacion de contrasena.
- No hay aprendizaje supervisado ni evaluacion offline etiquetada.
