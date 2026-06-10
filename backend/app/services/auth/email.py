import logging
from typing import Protocol

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.auth import EmailOutbox, EmailOutboxStatus
from app.models.user import User
from app.services.auth.account_tokens import utc_now

logger = logging.getLogger(__name__)


class EmailService(Protocol):
    def send_verification_email(
        self,
        *,
        recipient: str,
        verification_url: str,
        full_name: str | None,
    ) -> str | None: ...


class ConsoleEmailService:
    def send_verification_email(
        self,
        *,
        recipient: str,
        verification_url: str,
        full_name: str | None,
    ) -> str | None:
        logger.warning(
            "EMAIL VERIFICATION | recipient=%s | name=%s | url=%s",
            recipient,
            full_name or "",
            verification_url,
        )
        return None


class FakeEmailService:
    def __init__(self) -> None:
        self.messages: list[dict[str, str | None]] = []

    def send_verification_email(
        self,
        *,
        recipient: str,
        verification_url: str,
        full_name: str | None,
    ) -> str | None:
        self.messages.append(
            {
                "recipient": recipient,
                "verification_url": verification_url,
                "full_name": full_name,
            }
        )
        return f"fake-{len(self.messages)}"


def get_email_service() -> EmailService:
    if settings.EMAIL_PROVIDER == "fake":
        return FakeEmailService()
    return ConsoleEmailService()


def build_verification_url(raw_token: str) -> str:
    frontend_url = settings.FRONTEND_URL.rstrip("/")
    return f"{frontend_url}/verify-email?token={raw_token}"


def create_verification_outbox(db: Session, user: User) -> EmailOutbox:
    outbox = EmailOutbox(
        recipient=user.email,
        template="email_verification",
        variables={
            "full_name": user.full_name or "",
            "verification_path": "/verify-email",
        },
        status=EmailOutboxStatus.PENDING,
        attempts=0,
        next_attempt_at=utc_now(),
    )
    db.add(outbox)
    return outbox


def deliver_verification_email(
    db: Session,
    *,
    outbox: EmailOutbox,
    user: User,
    raw_token: str,
    email_service: EmailService | None = None,
) -> None:
    service = email_service or get_email_service()
    outbox.status = EmailOutboxStatus.SENDING
    outbox.attempts += 1
    outbox.updated_at = utc_now()
    try:
        outbox.provider_message_id = service.send_verification_email(
            recipient=user.email,
            verification_url=build_verification_url(raw_token),
            full_name=user.full_name,
        )
        outbox.status = EmailOutboxStatus.SENT
    except Exception:
        logger.exception("No se pudo enviar el correo de verificacion a %s", user.email)
        outbox.status = EmailOutboxStatus.FAILED
    finally:
        outbox.updated_at = utc_now()
        db.commit()
