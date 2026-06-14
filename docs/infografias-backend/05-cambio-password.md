# 05. Cambio de contraseña desde Ajustes

## Diagrama

```mermaid
flowchart TD
    U["Usuario autenticado"] --> A["SettingsComponent"]
    A -->|"POST /api/v1/auth/change-password"| ORIGIN["AuthenticatedOriginMiddleware"]
    ORIGIN --> ACTIVE["Depends(get_active_user)"]
    ACTIVE --> CURRENT["Depends(get_current_session)"]
    CURRENT --> RL["Rate limit por user_id<br/>5 por hora"]
    RL --> VERIFY["verify_password(current_password)"]
    VERIFY -->|incorrecta| E400["400 mensaje genérico"]
    VERIFY -->|correcta| VALIDATE["PasswordChange<br/>10-128 + confirmación"]
    VALIDATE --> SAME{"¿Nueva igual a actual?"}
    SAME -->|Sí| EDIFF["400 debe ser diferente"]
    SAME -->|No| ARGON["hash_password()<br/>Argon2id"]
    ARGON --> UPDATE["Actualizar hashed_password<br/>password_changed_at"]
    UPDATE --> TOKENS["Invalidar password_reset pendientes"]
    TOKENS --> REVOKE["revoke_user_sessions()<br/>except_session_id=current_session.id"]
    REVOKE --> COMMIT["COMMIT"]
    COMMIT --> OK["200 Contraseña actualizada correctamente"]
```

## Explicación

Este flujo requiere simultáneamente:

- una sesión opaca válida;
- un usuario `active`;
- `email_verified_at` no nulo.

`get_active_user` deriva de `get_current_user`, que a su vez depende de
`get_current_session`. La función del endpoint recibe además `current_session` para
conocer qué sesión debe conservar.

La contraseña actual se verifica con `verify_password()`, compatible con Argon2 y
bcrypt. La nueva contraseña siempre se guarda mediante `hash_password()`, por lo que
el resultado es Argon2id.

## Diferencia respecto al reset

| Operación | Sesión actual | Otras sesiones |
|---|---|---|
| `reset-password` | Revocada | Revocadas |
| `change-password` | Se conserva | Revocadas |

## Archivos implicados

- `backend/app/api/v1/endpoints/auth.py`: `change_password()`.
- `backend/app/api/deps.py`: `get_active_user()`, `get_current_session()`.
- `backend/app/schemas/auth.py`: `PasswordChange`.
- `backend/app/core/security.py`: `verify_password()`, `hash_password()`.
- `backend/app/services/auth/account_tokens.py`: `invalidate_account_tokens()`.
- `backend/app/services/auth/sessions.py`: `revoke_user_sessions()`.
- `frontend/src/app/features/settings/settings.component.ts`.
- `frontend/src/app/features/auth/auth.service.ts`: `changePassword()`.

## Seguridad

- La respuesta a una contraseña actual incorrecta es deliberadamente genérica.
- La confirmación se valida tanto en Angular como en Pydantic.
- Los tokens de recuperación pendientes dejan de ser útiles.
- La cookie actual no se rota; la sesión actual se conserva explícitamente.
- No existe historial de contraseñas ni comprobación contra contraseñas filtradas.
  Esa funcionalidad no está implementada.

