# 06. `email_outbox` y `email-worker`

## Flujo de procesamiento

```mermaid
sequenceDiagram
    participant API as Endpoint FastAPI
    participant C as EmailPayloadCipher
    participant DB as PostgreSQL
    participant W as email-worker
    participant P as EmailService

    API->>C: encrypt({raw_token})
    C-->>API: encrypted_payload Fernet
    API->>DB: INSERT email_outbox pending
    API-->>API: responder sin esperar envío

    loop Cada EMAIL_WORKER_POLL_SECONDS
        W->>DB: cancel_legacy_messages()
        W->>DB: recover_abandoned_messages()
        W->>DB: SELECT pending due<br/>FOR UPDATE SKIP LOCKED
        W->>DB: status=sending, attempts++, COMMIT
        W->>DB: cargar mensaje por id
        W->>C: decrypt(encrypted_payload)
        W->>DB: validar AccountToken y usuario
        W->>P: send(EmailMessage)

        alt envío correcto
            W->>DB: status=sent, provider_message_id<br/>encrypted_payload=NULL
        else fallo temporal y quedan intentos
            W->>DB: status=pending<br/>next_attempt_at según calendario
        else fallo permanente o intentos agotados
            W->>DB: status=failed<br/>encrypted_payload=NULL
        else token inválido, usado o caducado
            W->>DB: status=cancelled<br/>encrypted_payload=NULL
        end
    end
```

## Máquina de estados

```mermaid
flowchart TD
    PENDING["pending"] -->|"claim_due_messages()"| SENDING["sending"]
    SENDING -->|"proveedor acepta"| SENT["sent"]
    SENDING -->|"error temporal"| PENDING
    SENDING -->|"error permanente"| FAILED["failed"]
    SENDING -->|"se agotan 6 intentos"| FAILED
    SENDING -->|"token/usuario ya no válido"| CANCELLED["cancelled"]
    SENDING -->|"worker cae y supera stale threshold"| PENDING
    PENDING -->|"fila legacy sin encrypted_payload"| CANCELLED

    SENT --> CLEAR1["encrypted_payload = NULL"]
    FAILED --> CLEAR2["encrypted_payload = NULL"]
    CANCELLED --> CLEAR3["encrypted_payload = NULL"]
```

## Reintentos

`RETRY_DELAYS` contiene:

1. 1 minuto.
2. 5 minutos.
3. 15 minutos.
4. 60 minutos.
5. 240 minutos.

`EMAIL_MAX_ATTEMPTS=6` representa el intento inicial más cinco reintentos.

Brevo considera temporales:

- errores de transporte de `httpx`;
- HTTP `429`;
- HTTP `5xx`.

Los demás HTTP `4xx` son permanentes. Un payload Fernet corrupto también falla sin
reintento.

## Proveedores

```mermaid
flowchart TD
    SELECT["get_email_service()"] --> ENV{"EMAIL_PROVIDER"}
    ENV -->|"console"| CONSOLE["ConsoleEmailService<br/>logs en desarrollo"]
    ENV -->|"brevo"| BREVO["BrevoEmailService<br/>httpx + API key"]
    ENV -->|"fake"| FAKE["FakeEmailService<br/>captura mensajes en tests"]
```

`ConsoleEmailService` muestra contenido y enlace en desarrollo. Si se instancia en
producción, solo registra `EMAIL SENT TO CONSOLE`, sin destinatario ni contenido.
La configuración productiva, además, obliga a usar `brevo`.

## Archivos implicados

- `backend/app/models/auth.py`: `EmailOutbox`, `EmailOutboxStatus`.
- `backend/app/services/email/contracts.py`: `EmailService`, `EmailMessage`,
  `EmailDeliveryError`.
- `backend/app/services/email/crypto.py`: Fernet.
- `backend/app/services/email/outbox.py`: encolado, reclamación y procesamiento.
- `backend/app/services/email/providers.py`: Console, Fake y Brevo.
- `backend/app/services/email/templates.py`: HTML y texto.
- `backend/app/workers/email_worker.py`: bucle y parada por señales.
- `backend/alembic/versions/20260611_0009_email_outbox_worker.py`.
- `docker-compose.yml`: servicio `email-worker`.

## Puntos clave

- `FOR UPDATE SKIP LOCKED` permite varios workers sin reclamar la misma fila.
- La entrega es al menos una vez: una caída después de aceptar Brevo y antes del
  commit podría causar un duplicado.
- `recover_abandoned_messages()` recupera `sending` antiguos.
- `last_error` se sanitiza y limita a 1000 caracteres.
- Los logs normales del worker contienen ID y estado, no token ni payload.
- Rotar `EMAIL_PAYLOAD_ENCRYPTION_KEY` sin migrar filas pendientes impediría
  descifrarlas.

