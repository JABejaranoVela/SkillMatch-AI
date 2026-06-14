# Modelo De Datos

## Identidad Y Seguridad

### `users`

Cuenta de usuario:

- email unico y password hasheada;
- nombre y rol;
- estado `pending`, `active` o `disabled`;
- fecha de verificacion, ultimo login y cambio de contrasena.

Los usuarios existentes al aplicar la migracion de autenticacion se conservan como
activos y verificados.

### `auth_sessions`

Sesiones opacas:

- hash del token y hash CSRF preparado;
- expiracion, ultimo uso y revocacion;
- IP y user-agent opcionales.

El token en claro solo vive en la cookie HttpOnly.

### `account_tokens`

Tokens de cuenta:

- usuario y proposito;
- hash unico;
- expiracion, uso y creacion.

Los propositos implementados son `email_verification` y `password_reset`. Ambos
guardan solo el hash, tienen caducidad y son de un solo uso.

### `email_outbox`

Cola persistente de correo:

- destinatario, plantilla y variables no sensibles;
- FK opcional al token de cuenta que origina el correo;
- payload sensible cifrado con Fernet;
- estado, intentos, siguiente intento y ultimo intento;
- identificador del proveedor y ultimo error sanitizado.

Estados: `pending`, `sending`, `sent`, `failed` y `cancelled`. Los payloads se
eliminan al enviar, cancelar o agotar reintentos. La migracion `20260611_0009`
cancela filas legacy `pending`/`sending` que no tienen payload cifrado.

### `auth_rate_limit_buckets`

Ventanas persistentes contra abuso:

- clave HMAC-SHA256 unica y accion;
- contador, inicio y expiracion de ventana;
- fechas de creacion y actualizacion.

La clave combina accion, ventana e identificadores normalizados. No permite
recuperar el email o la IP usados para construirla.

## CV Y Perfil

### `resumes`

- propietario, nombre, ruta y tipo;
- estado de procesamiento;
- texto bruto y limpio;
- indicador de CV activo;
- fechas de creacion/procesamiento.

### `professional_profiles`

Perfil uno-a-uno con un CV:

- tipo y resumen;
- experiencia estimada;
- formacion, idiomas, tecnologias y analisis JSON;
- embedding pgvector de 384 dimensiones.

### `skills`

Catalogo normalizado con nombre, nombre canonico, categoria y aliases.

### `profile_skills`

Relacion perfil-skill con confianza y origen (`dictionary`, `pattern` o `ner`).

## Ofertas

### `jobs`

- titulo, empresa, descripcion y requisitos;
- ubicacion, modalidad, salario y contrato;
- fuente, ID externo y URL;
- estado y fecha de publicacion;
- embedding pgvector de 384 dimensiones.

La combinacion `(source, external_id)` es unica.

### `job_skills`

Relacion oferta-skill con nivel y peso opcionales.

### `job_imports`

Auditoria de importaciones con fuente, estado y contadores.

### `job_search_tasks`

Estado de una busqueda asincrona por usuario:

- identificador publico;
- fase, mensaje y fuentes;
- importados, actualizados, omitidos y error.

## Matching Y Feedback

### `match_results`

- usuario, CV y oferta;
- score de reglas, semantico y final;
- explicacion JSON;
- version del algoritmo y fecha.

### `user_job_interactions`

Registra `viewed`, `saved`, `discarded` o `applied`, asociado opcionalmente al
resultado de matching que vio el usuario.

## Relaciones Principales

```text
users
  |-- auth_sessions
  |-- account_tokens -- email_outbox
  |-- auth_rate_limit_buckets (sin FK; claves anonimizadas)
  |-- resumes -- professional_profiles -- profile_skills -- skills
  |-- match_results -- jobs -- job_skills -- skills
  |-- user_job_interactions -- jobs
  `-- job_search_tasks
```

`email_outbox` no contiene una FK directa al usuario. Para verificacion enlaza el
`account_token` y mantiene `ON DELETE SET NULL`, lo que permite cancelar el mensaje
si el token desaparece sin acoplar la cola a un unico tipo de correo.

## Principios

- Separar documento, texto extraido y perfil estructurado.
- Guardar hashes, nunca tokens de autenticacion en claro.
- Cifrar cualquier secreto temporal que el worker necesite recuperar.
- Versionar resultados de matching.
- Mantener explicaciones como JSON estructurado.
- Conservar la fuente y URL original de cada oferta.
- Tratar CV y correo como datos personales.
