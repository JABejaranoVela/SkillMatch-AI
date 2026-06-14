# API

Prefijo: `/api/v1`

La especificacion ejecutable esta disponible en `/docs` y `/api/v1/openapi.json`.

## Autenticacion

| Metodo | Ruta | Acceso | Descripcion |
|---|---|---|---|
| POST | `/auth/register` | Publico | Registro generico; crea usuario pendiente si procede |
| POST | `/auth/verify-email` | Publico | Consume token de verificacion |
| POST | `/auth/resend-verification` | Pending | Reenvia con cooldown de 60 segundos |
| POST | `/auth/forgot-password` | Publico | Encola recuperacion con respuesta generica |
| POST | `/auth/reset-password` | Publico | Consume token y revoca todas las sesiones |
| POST | `/auth/login` | Publico | Crea sesion y cookie HttpOnly |
| POST | `/auth/logout` | Publico/sesion | Revoca la sesion y elimina cookie |
| GET | `/auth/session` | Autenticado | Restaura usuario desde cookie |
| GET | `/auth/me` | Autenticado | Devuelve la cuenta actual |
| PATCH | `/auth/me` | Autenticado | Actualiza el nombre |
| POST | `/auth/change-password` | Activo | Cambia la contrasena y revoca otras sesiones |

`POST /auth/register` devuelve `202` y un mensaje generico tanto si el correo ya
existe como si el registro se acepta. Cuando crea una cuenta, el correo queda
encolado y la respuesta no espera a Console/Brevo.

`POST /auth/resend-verification` invalida tokens anteriores, crea uno nuevo y
encola otro correo. El worker cancelara cualquier fila anterior cuyo token ya no
sea valido.

`POST /auth/forgot-password` devuelve siempre `202` y el mismo mensaje. Solo crea
token y outbox para usuarios activos y verificados, con un maximo de cinco
solicitudes por usuario y hora.

`POST /auth/reset-password` exige token, `new_password` y `confirm_password`. El
token dura 60 minutos, es de un solo uso y el cambio revoca todas las sesiones.

`POST /auth/change-password` exige contrasena actual, nueva y confirmacion. Mantiene
la sesion actual y revoca las demas.

Las escrituras autenticadas con cookie requieren una cabecera `Origin` permitida.
Login, registro, reenvio y recuperacion aplican limites persistentes. Registro y
`forgot-password` mantienen su respuesta generica aunque se alcance el limite.

## CV

Todos requieren usuario activo y correo verificado.

| Metodo | Ruta | Descripcion |
|---|---|---|
| POST | `/resumes/upload` | Sube PDF/DOCX y lo marca como CV activo |
| GET | `/resumes` | Lista el CV activo del usuario |
| GET | `/resumes/active` | Obtiene el CV activo |
| GET | `/resumes/active/profile` | Obtiene su perfil profesional |
| GET | `/resumes/{resume_id}` | Obtiene un CV propio |
| GET | `/resumes/{resume_id}/profile` | Obtiene el perfil de un CV propio |
| POST | `/resumes/{resume_id}/process` | Procesa o reprocesa el CV |

## Ofertas

Todos requieren usuario activo y correo verificado.

| Metodo | Ruta | Descripcion |
|---|---|---|
| GET | `/jobs` | Lista ofertas recomendables importadas |
| POST | `/jobs` | Admin: crea una oferta tecnica/manual |
| POST | `/jobs/import` | Admin: importa un archivo CSV o JSON |
| POST | `/jobs/search/profile` | Inicia busqueda asincrona para el perfil |
| GET | `/jobs/search/{task_id}` | Consulta el estado de la busqueda |
| GET | `/jobs/recommended` | Ranking paginado del CV activo |
| GET | `/jobs/{job_id}` | Detalle de una oferta recomendable |

Parametros de `/jobs/recommended`:

- `limit`: 1-50, por defecto 20.
- `offset`: desplazamiento, por defecto 0.

Respuesta: `items`, `total`, `limit`, `offset` y `has_more`.

## Feedback

Todos requieren usuario activo y correo verificado.

| Metodo | Ruta | Descripcion |
|---|---|---|
| POST | `/feedback` | Registra `viewed`, `saved`, `discarded` o `applied` |
| GET | `/feedback/me` | Lista interacciones del usuario |
| GET | `/feedback/me/jobs` | Lista ofertas guardadas/postuladas con score |

`/feedback/me/jobs` acepta `interaction_type` para filtrar.

## Salud

| Metodo | Ruta | Acceso | Descripcion |
|---|---|---|---|
| GET | `/health` | Publico | Estado basico del backend |

## Codigos Relevantes

- `202`: registro aceptado o busqueda iniciada.
- `401`: sesion ausente o invalida.
- `403`: cuenta deshabilitada o correo sin verificar.
- `409`: conflicto de estado o token ya usado.
- `410`: token de verificacion caducado.
- `429`: cooldown o rate limit; incluye `Retry-After` cuando no afecta a una
  respuesta publica generica.
