# 03. Login y sesiones opacas

## Diagrama de secuencia

```mermaid
sequenceDiagram
    actor U as Usuario
    participant A as Angular LoginComponent
    participant S as AuthService
    participant API as FastAPI auth.login
    participant RL as Rate limiter
    participant DB as PostgreSQL
    participant C as Navegador / Cookie
    participant G as Angular guards

    U->>A: Email y contraseña
    A->>S: login(email, password)
    S->>API: POST /api/v1/auth/login<br/>OAuth2PasswordRequestForm
    API->>API: normalize_email()
    API->>RL: bucket login(IP + email)
    RL->>DB: UPSERT auth_rate_limit_buckets
    API->>DB: SELECT User por lower(email)
    API->>API: verify_password_and_update()

    alt hash bcrypt válido
        API->>API: generar hash Argon2id
        API->>DB: actualizar hashed_password
    end

    alt usuario disabled
        API-->>S: 403
    else credenciales inválidas
        API-->>S: 401
    else pending o active
        API->>API: generate_session_token()
        API->>DB: INSERT auth_sessions con SHA-256
        API->>DB: last_login_at=now y COMMIT
        API-->>C: Set-Cookie skillmatch_session<br/>HttpOnly, SameSite, Secure configurable
        API-->>S: UserRead
        S->>S: guardar usuario en BehaviorSubject
    end

    Note over S,API: Al arrancar Angular
    S->>API: GET /api/v1/auth/session
    C-->>API: cookie automática
    API->>DB: hash cookie y buscar AuthSession
    API->>API: comprobar expires_at y revoked_at
    API->>DB: touch last_seen_at si pasaron 5 min
    API-->>S: UserRead o 401/403
    S->>G: waitForUser() / waitForSession()
    G-->>U: permitir ruta o redirigir
```

## Qué es una sesión opaca

El token de sesión es un valor aleatorio generado con
`secrets.token_urlsafe(48)`. No contiene email, rol, expiración ni claims. Por eso
es "opaco": solo PostgreSQL puede resolverlo.

```mermaid
flowchart TD
    RAW["Token original aleatorio"] --> COOKIE["Cookie HttpOnly en navegador"]
    RAW --> SHA["SHA-256"]
    SHA --> DB[("auth_sessions.token_hash")]
    COOKIE --> REQUEST["Petición posterior"]
    REQUEST --> HASH2["SHA-256 de la cookie"]
    HASH2 --> LOOKUP["find_session()"]
    LOOKUP --> DB
```

## Comportamiento por estado

- `pending`: puede iniciar sesión y consultar `/auth/session`, pero los endpoints de
  CV, ofertas y feedback fallan en `get_active_user`.
- `active` verificado: acceso normal.
- `disabled`: login devuelve `403`; una sesión ya existente también es rechazada por
  `get_current_session`.

`OAuth2PasswordRequestForm` solo define el formato `username/password`. El backend
no emite un bearer token, no implementa OAuth2 y no usa JWT.

## Ciclo de vida

- Duración: `SESSION_DAYS`, por defecto 30 días.
- Actividad: `touch_session()` actualiza `last_seen_at` como máximo cada 5 minutos.
- No existe renovación deslizante de `expires_at`.
- Login con una cookie previa revoca esa sesión antes de crear otra.
- Logout marca `revoked_at` y elimina la cookie.
- Reset de contraseña revoca todas las sesiones.
- Cambio desde Ajustes conserva solo la sesión actual.

## Archivos implicados

- `backend/app/api/v1/endpoints/auth.py`: `login()`, `session()`, `logout()`.
- `backend/app/services/auth/sessions.py`: generación, hash, búsqueda y revocación.
- `backend/app/core/security.py`: Argon2id y compatibilidad bcrypt.
- `backend/app/api/deps.py`: `get_current_session()`, `get_current_user()`.
- `backend/app/models/auth.py`: `AuthSession`.
- `frontend/src/app/features/auth/auth.service.ts`: `login()`, `restoreSession()`.
- `frontend/src/app/core/auth.interceptor.ts`: `withCredentials`.
- `frontend/src/app/core/auth.guard.ts`: guards.

## Seguridad

- Solo el hash de la sesión se persiste.
- La cookie es `HttpOnly`, `Path=/`, `SameSite=Lax` por defecto y `Secure` obligatorio
  en producción.
- No se utiliza `localStorage` ni `sessionStorage`.
- `last_seen_at` sirve para actividad operativa, no para prolongar la sesión.
- IP y user-agent se guardan en claro en `auth_sessions`.

