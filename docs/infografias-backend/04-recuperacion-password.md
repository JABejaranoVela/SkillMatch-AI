# 04. Recuperación de contraseña

## Diagrama de secuencia

```mermaid
sequenceDiagram
    actor U as Usuario
    participant A as Angular ForgotPassword
    participant API as FastAPI
    participant RL as Rate limiter
    participant DB as PostgreSQL
    participant O as email_outbox
    participant W as email-worker
    participant E as Console/Brevo

    U->>A: Introduce email
    A->>API: POST /api/v1/auth/forgot-password
    API->>API: ForgotPasswordRequest + normalize_email()
    API->>RL: bucket por IP y bucket por email
    RL->>DB: UPSERT contadores HMAC
    API->>DB: SELECT User FOR UPDATE

    alt inexistente, pending, disabled, no verificado o limitado
        API-->>A: 202 mensaje genérico
    else active y verificado
        API->>DB: invalidar password_reset anteriores
        API->>DB: INSERT account_token<br/>SHA-256, TTL 60 min
        API->>O: enqueue_password_reset_email()
        O->>O: cifrar raw token con Fernet
        O->>DB: INSERT pending
        API->>DB: COMMIT
        API-->>A: 202 mensaje genérico
    end

    W->>DB: reclamar outbox
    W->>W: descifrar y revalidar token/usuario
    W->>E: enviar enlace /reset-password?token=...
    E-->>U: Correo de recuperación

    U->>API: POST /api/v1/auth/reset-password
    API->>RL: bucket reset_password por IP
    API->>DB: buscar token_hash + purpose FOR UPDATE
    API->>API: validar uso, caducidad y usuario active
    API->>API: validar 10-128 y confirmación
    API->>API: hash_password() Argon2id
    API->>DB: actualizar hashed_password y password_changed_at
    API->>DB: used_at=now e invalidar otros tokens
    API->>DB: revocar todas las auth_sessions
    API->>DB: COMMIT
    API-->>U: Contraseña restablecida
```

## Explicación

`forgot_password()` está diseñado contra enumeración de usuarios. La respuesta
pública es siempre la misma, incluso si:

- el email no existe;
- la cuenta está `pending` o `disabled`;
- no está verificada;
- se ha alcanzado un límite.

El token se genera con `create_password_reset_token()`. Su hash queda en
`account_tokens`; el valor original solo queda recuperable dentro de
`email_outbox.encrypted_payload`.

`reset_password()` diferencia internamente token inexistente (`400`), usado (`409`)
y caducado (`410`), pero usa el mismo mensaje prudente:
`INVALID_RESET_LINK_MESSAGE`.

## Límites actuales

- TTL: `PASSWORD_RESET_TTL_MINUTES`, 60 por defecto.
- Por email/usuario: 5 solicitudes por hora.
- Por IP en `forgot-password`: 20 por hora.
- `reset-password`: 10 intentos por hora por IP.
- Un nuevo token invalida los anteriores sin usar.

## Archivos implicados

- `backend/app/api/v1/endpoints/auth.py`: `forgot_password()`, `reset_password()`.
- `backend/app/schemas/auth.py`: `ForgotPasswordRequest`,
  `ResetPasswordRequest`.
- `backend/app/services/auth/account_tokens.py`:
  `create_password_reset_token()`, `find_password_reset_token()`.
- `backend/app/services/email/outbox.py`: `enqueue_password_reset_email()`.
- `backend/app/services/email/templates.py`: `build_password_reset_url()`,
  `render_password_reset_email()`.
- `backend/app/services/auth/sessions.py`: `revoke_user_sessions()`.
- `frontend/src/app/features/auth/forgot-password.component.ts`.
- `frontend/src/app/features/auth/reset-password.component.ts`.

## Seguridad

- El endpoint no envía correo directamente.
- El worker cancela el correo si el token o el usuario dejan de ser válidos.
- El reset consume el token antes de confirmar la transacción.
- Todas las sesiones quedan revocadas para obligar a autenticarse con la nueva
  contraseña.
- La nueva contraseña nunca se guarda ni se introduce en logs.

