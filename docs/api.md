# API

Prefijo: `/api/v1`.

La especificacion ejecutable esta disponible en desarrollo en `/docs` y
`/openapi.json`. En `ENVIRONMENT=production`, Swagger, ReDoc y OpenAPI quedan
deshabilitados.

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

## Demo Publica

| Metodo | Ruta | Acceso | Descripcion |
|---|---|---|---|
| POST | `/public/demo/analyze-cv` | Publico | Analiza un PDF en memoria sin persistirlo |

La demo publica acepta solo PDF, aplica limite de tamano, limite de paginas,
minimo de texto extraible y rate limit por IP. No crea `Resume`,
`ProfessionalProfile`, embeddings, resultados ni feedback.

## CV

Todos requieren usuario activo y correo verificado.

| Metodo | Ruta | Descripcion |
|---|---|---|
| POST | `/resumes/upload` | Sube un PDF validado y lo procesa como CV activo |
| GET | `/resumes` | Lista el CV activo del usuario |
| GET | `/resumes/active` | Obtiene el CV activo |
| GET | `/resumes/active/profile` | Obtiene su perfil profesional |
| GET | `/resumes/{resume_id}` | Obtiene un CV propio |
| GET | `/resumes/{resume_id}/profile` | Obtiene el perfil de un CV propio |
| DELETE | `/resumes/{resume_id}` | Elimina un CV propio y sus datos derivados |
| POST | `/resumes/{resume_id}/process` | Procesa o reprocesa el CV |

DOCX no es un formato aceptado en produccion. Si se sube un `.docx`, la API debe
responder con error seguro de tipo no permitido.

La eliminacion de CV borra el archivo fisico si existe, elimina perfil,
`profile_skills` y `match_results`, y desvincula `UserJobInteraction.match_result_id`
cuando esas interacciones apuntan a resultados del CV eliminado. No borra ofertas,
skills globales ni jobs globales.

## Ofertas

Todos requieren usuario activo y correo verificado, salvo endpoints admin que
requieren usuario administrador activo.

| Metodo | Ruta | Descripcion |
|---|---|---|
| GET | `/jobs` | Lista ofertas recomendables importadas |
| POST | `/jobs` | Admin: crea una oferta tecnica/manual |
| POST | `/jobs/import` | Admin: importa un archivo CSV o JSON |
| POST | `/jobs/search/profile` | Inicia busqueda asincrona para el perfil |
| GET | `/jobs/search/{task_id}` | Consulta el estado de la busqueda propia |
| GET | `/jobs/recommended` | Ranking paginado del CV activo |
| GET | `/jobs/{job_id}` | Detalle de una oferta recomendable |

`POST /jobs/search/profile` no permite iniciar otra busqueda si el usuario ya
tiene una tarea activa en `pending`, `processing`, `searching`, `importing` o
`ranking`; responde `409` con mensaje seguro. Si supera el limite horario,
responde `429` con `Retry-After`.

Los errores internos de busqueda no se exponen al frontend. El mensaje seguro es:
`No se ha podido completar la busqueda de ofertas en este momento.`

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

`/feedback/me/jobs` acepta `interaction_type` para filtrar. Si se envia
`match_result_id`, debe pertenecer al usuario autenticado y coincidir con la oferta
indicada.

## Salud

| Metodo | Ruta | Acceso | Descripcion |
|---|---|---|---|
| GET | `/health` | Publico | Estado basico del backend |

## Codigos Relevantes

- `202`: registro aceptado o busqueda iniciada.
- `400`: archivo no valido o datos de entrada invalidos.
- `401`: sesion ausente o invalida.
- `403`: cuenta deshabilitada o correo sin verificar.
- `404`: recurso inexistente o no perteneciente al usuario.
- `409`: conflicto de estado, token ya usado o busqueda ya activa.
- `410`: token de verificacion o recuperacion caducado.
- `413`: archivo demasiado grande.
- `429`: cooldown o rate limit; incluye `Retry-After` cuando no afecta a una
  respuesta publica generica.
