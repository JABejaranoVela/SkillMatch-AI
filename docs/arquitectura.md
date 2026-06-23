# Arquitectura

## Vision General

SkillMatch AI usa una arquitectura web con API, base de datos relacional/vectorial
y procesos desacoplados:

```text
Angular 20 + Nginx
    |
    | REST + cookie HttpOnly
    v
FastAPI / SQLAlchemy / servicios de dominio
    |
    +----------> PostgreSQL 16 + pgvector + email_outbox
                                      |
                                      v
                              email-worker -> Console/Brevo/Fake
```

Docker Compose levanta base de datos, backend, worker de correo y frontend. En
produccion, Nginx sirve la aplicacion Angular compilada y proxifica `/api` hacia
FastAPI. El entorno de desarrollo y el de produccion usan Compose/Dockerfiles y
tags de imagen separados.

## Frontend

La aplicacion Angular contiene:

- `core/`: interceptor de credenciales y guards.
- `features/auth/`: login, registro, verificacion y recuperacion de contrasena.
- `features/landing/`: landing publica y demo de analisis de CV.
- `features/dashboard/`: inicio privado del usuario.
- `features/resumes/`: subida con aviso informativo, procesamiento, perfil y borrado de CV.
- `features/jobs/`: busqueda y recomendaciones.
- `features/saved-jobs/`: ofertas guardadas/postuladas.
- `features/profile/` y `features/settings/`: cuenta y cambio de contrasena.

`AuthService` restaura la sesion al arrancar. `verifiedGuard` exige usuario activo y
correo verificado en las rutas privadas. El frontend no persiste tokens; todas las
solicitudes usan cookie HttpOnly y las escrituras autenticadas envian `Origin`.

## Backend

FastAPI organiza la API en:

- `api/deps.py`: sesion actual, usuario actual, usuario activo y usuario pendiente.
- `api/v1/endpoints/`: auth, public, resumes, jobs, feedback y health.
- `services/auth/`: sesiones, tokens, rate limiting e identificadores.
- `services/email/`: contratos, cifrado, plantillas, outbox y proveedores.
- `workers/email_worker.py`: reclamacion y entrega de correos encolados.
- `services/cv_processing/`: almacenamiento, extraccion PDF y perfil.
- `services/nlp/`: normalizacion, skills, taxonomia y NER opcional.
- `services/jobs_import/`: Tecnoempleo, InfoJobs, importacion y upsert.
- `services/embeddings/`: generacion y similitud vectorial.
- `services/matching/`: reglas y score hibrido.
- `services/maintenance/`: cleanup de datos temporales y estados abandonados.

Las tareas de busqueda se ejecutan con `BackgroundTasks` y persisten su estado en
`job_search_tasks`. Esta solucion es suficiente para staging/controlado, pero no
sustituye una cola durable.

## Flujo De Autenticacion

1. El registro crea un usuario `pending`.
2. Se crea un token aleatorio y solo se persiste su hash en `account_tokens`.
3. El token en claro se cifra con Fernet en `email_outbox`; la peticion termina sin
   esperar al proveedor.
4. `email-worker` reclama filas con `FOR UPDATE SKIP LOCKED`, valida el token y
   entrega por consola o Brevo.
5. Los fallos transitorios se reintentan a 1, 5, 15, 60 y 240 minutos.
6. Login crea una sesion opaca y una cookie HttpOnly.
7. La verificacion bloquea la fila del token, valida uso/caducidad y activa al usuario.
8. Backend y frontend impiden que un usuario pendiente use CV, ofertas o feedback.

Un middleware rechaza `POST`, `PUT`, `PATCH` y `DELETE` con cookie de sesion si
falta `Origin` o no coincide con `FRONTEND_URL`/CORS. Los flujos sensibles consumen
buckets de rate limiting en PostgreSQL mediante una operacion atomica.

El worker recupera filas `sending` abandonadas tras el umbral configurado. Cancela
mensajes si el token fue usado, caduco, se invalido o ya no coincide con su hash.
Tras enviar, fallar definitivamente o cancelar, elimina el payload cifrado.

## Flujo De CV

1. El usuario ve un aviso informativo de tratamiento del CV en frontend.
2. El backend acepta solo PDF.
3. Se valida extension, MIME, cabecera `%PDF`, parseo real con PyMuPDF, paginas,
   tamano y texto minimo extraible.
4. El archivo se guarda fuera del repositorio.
5. Si el procesamiento falla, el CV queda `failed` y no queda activo.
6. Se desactiva el CV anterior solo cuando el nuevo flujo es valido.
7. Se normaliza el contenido.
8. Se detectan skills, evidencias, experiencia, idiomas y formacion.
9. Se crea `professional_profiles` y su embedding.
10. El usuario puede eliminar su CV; se borran archivo, perfil, skills de perfil y
    resultados de matching asociados.

La demo publica reutiliza analisis en memoria, no persiste CV, perfil, embeddings
ni resultados.

## Flujo De Ofertas

1. El perfil genera terminos de busqueda.
2. Se impide lanzar una busqueda si el usuario ya tiene una tarea activa.
3. Se aplica rate limit por usuario/hora.
4. Tecnoempleo se consulta por defecto.
5. InfoJobs se consulta si existen credenciales.
6. Las ofertas se normalizan y actualizan por `(source, external_id)`.
7. Se generan embeddings cuando son necesarios.
8. Se calculan y persisten resultados para el CV activo.
9. El cleanup marca como `failed` las tareas activas abandonadas.

Los errores internos se registran de forma segura y el frontend recibe mensajes
genericos.

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
- PostgreSQL actua tambien como cola de correo para el volumen actual.
- PostgreSQL conserva buckets temporales de rate limiting; sus claves son HMAC y
  no contienen emails ni IPs recuperables.
- El filesystem local almacena CVs; la base conserva metadatos y ruta interna.
- Los CV, secretos, logs, backups, dumps y bases locales se excluyen mediante
  `.gitignore`.

## Despliegue

- `docker-compose.yml` queda para desarrollo.
- `docker-compose.prod.yml` queda para produccion/staging.
- El backend dev usa `skillmatch-ai-backend:dev`.
- Backend y worker productivos usan `skillmatch-ai-backend:prod`.
- Frontend productivo usa `skillmatch-ai-frontend:prod`.
- Nginx productivo sirve la SPA y proxifica `/api`.
- Las migraciones productivas se ejecutan manualmente tras backup.

## Limites Actuales

- `BackgroundTasks` no sustituye una cola distribuida.
- La entrega de correo es al menos una vez: una caida despues de aceptar Brevo y
  antes del commit puede provocar un duplicado.
- La rotacion de `EMAIL_PAYLOAD_ENCRYPTION_KEY` requiere vaciar o migrar payloads
  pendientes.
- `TRUST_PROXY_HEADERS` solo es seguro si el backend esta aislado detras de un proxy
  que sobrescribe la cabecera.
- Tecnoempleo depende de la estructura HTML del portal.
- No hay aprendizaje supervisado ni evaluacion offline etiquetada.
- Falta revision legal/RGPD completa antes de usuarios reales.
