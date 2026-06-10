from app.services.email.contracts import (
    EmailDeliveryError,
    EmailMessage,
    EmailSendResult,
    EmailService,
)
from app.services.email.outbox import (
    enqueue_password_reset_email,
    enqueue_verification_email,
)
from app.services.email.providers import (
    BrevoEmailService,
    ConsoleEmailService,
    FakeEmailService,
    get_email_service,
)

__all__ = [
    "BrevoEmailService",
    "ConsoleEmailService",
    "EmailDeliveryError",
    "EmailMessage",
    "EmailSendResult",
    "EmailService",
    "FakeEmailService",
    "enqueue_password_reset_email",
    "enqueue_verification_email",
    "get_email_service",
]
