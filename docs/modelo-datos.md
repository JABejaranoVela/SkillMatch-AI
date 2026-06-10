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

El proposito implementado es `email_verification`. El enum deja preparado
`password_reset`, pero el flujo de recuperacion no esta implementado.

### `email_outbox`

Cola persistente de correo:

- destinatario, plantilla y variables;
- estado, intentos y siguiente intento;
- identificador del proveedor.

Actualmente se usa con `ConsoleEmailService`.

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
  |-- account_tokens
  |-- resumes -- professional_profiles -- profile_skills -- skills
  |-- match_results -- jobs -- job_skills -- skills
  |-- user_job_interactions -- jobs
  `-- job_search_tasks
```

`email_outbox` no contiene una FK al usuario para mantenerlo desacoplado del tipo de
correo y permitir otros mensajes futuros.

## Principios

- Separar documento, texto extraido y perfil estructurado.
- Guardar hashes, nunca tokens de autenticacion en claro.
- Versionar resultados de matching.
- Mantener explicaciones como JSON estructurado.
- Conservar la fuente y URL original de cada oferta.
- Tratar CV y correo como datos personales.
