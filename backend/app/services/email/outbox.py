from datetime import datetime, timedelta, timezone
import hmac

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.auth import (
    AccountToken,
    AccountTokenPurpose,
    EmailOutbox,
    EmailOutboxStatus,
)
from app.models.user import User, UserStatus
from app.services.auth.account_tokens import hash_account_token, is_token_expired
from app.services.email.contracts import EmailDeliveryError, EmailService
from app.services.email.crypto import EmailPayloadCipher, EmailPayloadError
from app.services.email.providers import get_email_service
from app.services.email.templates import (
    EMAIL_VERIFICATION_TEMPLATE,
    PASSWORD_RESET_TEMPLATE,
    render_password_reset_email,
    render_verification_email,
)

RETRY_DELAYS = (
    timedelta(minutes=1),
    timedelta(minutes=5),
    timedelta(minutes=15),
    timedelta(minutes=60),
    timedelta(minutes=240),
)
MAX_ATTEMPTS = settings.EMAIL_MAX_ATTEMPTS
MAX_ERROR_LENGTH = 1000


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def enqueue_verification_email(
    db: Session,
    *,
    user: User,
    account_token: AccountToken,
    raw_token: str,
    cipher: EmailPayloadCipher | None = None,
) -> EmailOutbox:
    if account_token.id is None:
        db.flush()
    payload_cipher = cipher or EmailPayloadCipher()
    outbox = EmailOutbox(
        account_token_id=account_token.id,
        recipient=user.email,
        template=EMAIL_VERIFICATION_TEMPLATE,
        variables={"full_name": user.full_name or ""},
        encrypted_payload=payload_cipher.encrypt(
            {
                "version": 1,
                "verification_token": raw_token,
            }
        ),
        status=EmailOutboxStatus.PENDING,
        attempts=0,
        next_attempt_at=utc_now(),
    )
    db.add(outbox)
    return outbox


def enqueue_password_reset_email(
    db: Session,
    *,
    user: User,
    account_token: AccountToken,
    raw_token: str,
    cipher: EmailPayloadCipher | None = None,
) -> EmailOutbox:
    if account_token.id is None:
        db.flush()
    payload_cipher = cipher or EmailPayloadCipher()
    outbox = EmailOutbox(
        account_token_id=account_token.id,
        recipient=user.email,
        template=PASSWORD_RESET_TEMPLATE,
        variables={"full_name": user.full_name or ""},
        encrypted_payload=payload_cipher.encrypt(
            {
                "version": 1,
                "password_reset_token": raw_token,
            }
        ),
        status=EmailOutboxStatus.PENDING,
        attempts=0,
        next_attempt_at=utc_now(),
    )
    db.add(outbox)
    return outbox


def recover_abandoned_messages(
    db: Session,
    *,
    now: datetime | None = None,
) -> int:
    current_time = now or utc_now()
    stale_before = current_time - timedelta(
        minutes=settings.EMAIL_WORKER_STALE_MINUTES
    )
    result = db.execute(
        update(EmailOutbox)
        .where(
            EmailOutbox.status == EmailOutboxStatus.SENDING,
            EmailOutbox.encrypted_payload.is_not(None),
            (
                (EmailOutbox.last_attempt_at.is_not(None))
                & (EmailOutbox.last_attempt_at <= stale_before)
            )
            | (
                (EmailOutbox.last_attempt_at.is_(None))
                & (EmailOutbox.updated_at <= stale_before)
            ),
        )
        .values(
            status=EmailOutboxStatus.PENDING,
            next_attempt_at=current_time,
            last_error="Recovered abandoned email delivery",
            updated_at=current_time,
        )
    )
    return int(result.rowcount or 0)


def cancel_legacy_messages(
    db: Session,
    *,
    now: datetime | None = None,
) -> int:
    current_time = now or utc_now()
    result = db.execute(
        update(EmailOutbox)
        .where(
            EmailOutbox.status.in_(
                [EmailOutboxStatus.PENDING, EmailOutboxStatus.SENDING]
            ),
            EmailOutbox.encrypted_payload.is_(None),
        )
        .values(
            status=EmailOutboxStatus.CANCELLED,
            last_error="Encrypted email payload is missing",
            updated_at=current_time,
        )
    )
    return int(result.rowcount or 0)


def claim_due_messages(
    db: Session,
    *,
    now: datetime | None = None,
    batch_size: int | None = None,
) -> list[int]:
    current_time = now or utc_now()
    cancel_legacy_messages(db, now=current_time)
    recover_abandoned_messages(db, now=current_time)
    messages = list(
        db.scalars(
            select(EmailOutbox)
            .where(
                EmailOutbox.status == EmailOutboxStatus.PENDING,
                EmailOutbox.next_attempt_at <= current_time,
                EmailOutbox.encrypted_payload.is_not(None),
            )
            .order_by(EmailOutbox.next_attempt_at, EmailOutbox.id)
            .limit(batch_size or settings.EMAIL_WORKER_BATCH_SIZE)
            .with_for_update(skip_locked=True)
        )
    )
    for message in messages:
        message.status = EmailOutboxStatus.SENDING
        message.attempts += 1
        message.last_attempt_at = current_time
        message.last_error = None
        message.updated_at = current_time
    db.commit()
    return [message.id for message in messages]


def process_outbox_message(
    db: Session,
    message_id: int,
    *,
    email_service: EmailService | None = None,
    cipher: EmailPayloadCipher | None = None,
    now: datetime | None = None,
) -> EmailOutboxStatus | None:
    current_time = now or utc_now()
    outbox = db.get(EmailOutbox, message_id)
    if outbox is None or outbox.status != EmailOutboxStatus.SENDING:
        return None

    try:
        message = _build_message(
            db,
            outbox,
            cipher=cipher or EmailPayloadCipher(),
            now=current_time,
        )
    except InvalidOutboxEmail as exc:
        _cancel(outbox, str(exc), current_time)
        db.commit()
        return outbox.status
    except EmailPayloadError as exc:
        _handle_failure(
            outbox,
            EmailDeliveryError(str(exc), retryable=False),
            current_time,
        )
        db.commit()
        return outbox.status

    try:
        result = (email_service or get_email_service()).send(message)
    except EmailDeliveryError as exc:
        _handle_failure(outbox, exc, current_time)
    except Exception:
        _handle_failure(
            outbox,
            EmailDeliveryError(
                "Unexpected email provider error",
                retryable=True,
            ),
            current_time,
        )
    else:
        outbox.status = EmailOutboxStatus.SENT
        outbox.provider_message_id = result.provider_message_id
        outbox.last_error = None
        outbox.encrypted_payload = None
        outbox.updated_at = current_time
    db.commit()
    return outbox.status


class InvalidOutboxEmail(ValueError):
    pass


def _build_message(
    db: Session,
    outbox: EmailOutbox,
    *,
    cipher: EmailPayloadCipher,
    now: datetime,
):
    if not outbox.encrypted_payload or outbox.account_token_id is None:
        raise InvalidOutboxEmail("Email payload or account token is missing")

    payload = cipher.decrypt(outbox.encrypted_payload)
    if outbox.template == EMAIL_VERIFICATION_TEMPLATE:
        payload_key = "verification_token"
        expected_purpose = AccountTokenPurpose.EMAIL_VERIFICATION
    elif outbox.template == PASSWORD_RESET_TEMPLATE:
        payload_key = "password_reset_token"
        expected_purpose = AccountTokenPurpose.PASSWORD_RESET
    else:
        raise InvalidOutboxEmail("Unsupported email template")

    raw_token = payload.get(payload_key)
    if not isinstance(raw_token, str) or not raw_token:
        raise InvalidOutboxEmail("Account token is missing")

    account_token = db.get(AccountToken, outbox.account_token_id)
    if (
        account_token is None
        or account_token.purpose != expected_purpose
        or account_token.used_at is not None
        or is_token_expired(account_token, now)
        or not hmac.compare_digest(
            account_token.token_hash,
            hash_account_token(raw_token),
        )
    ):
        raise InvalidOutboxEmail("Account token is no longer valid")

    full_name = outbox.variables.get("full_name")
    normalized_full_name = full_name if isinstance(full_name, str) else None
    if outbox.template == PASSWORD_RESET_TEMPLATE:
        user = account_token.user
        if user.status != UserStatus.ACTIVE or user.email_verified_at is None:
            raise InvalidOutboxEmail("Password reset user is no longer eligible")
        return render_password_reset_email(
            recipient=outbox.recipient,
            full_name=normalized_full_name,
            raw_token=raw_token,
        )
    return render_verification_email(
        recipient=outbox.recipient,
        full_name=normalized_full_name,
        raw_token=raw_token,
    )


def _cancel(outbox: EmailOutbox, reason: str, now: datetime) -> None:
    outbox.status = EmailOutboxStatus.CANCELLED
    outbox.last_error = _sanitize_error(reason)
    outbox.encrypted_payload = None
    outbox.updated_at = now


def _handle_failure(
    outbox: EmailOutbox,
    error: EmailDeliveryError,
    now: datetime,
) -> None:
    outbox.last_error = _sanitize_error(str(error))
    outbox.updated_at = now
    if (
        error.retryable
        and outbox.attempts < settings.EMAIL_MAX_ATTEMPTS
        and outbox.attempts <= len(RETRY_DELAYS)
    ):
        outbox.status = EmailOutboxStatus.PENDING
        outbox.next_attempt_at = now + RETRY_DELAYS[outbox.attempts - 1]
        return
    outbox.status = EmailOutboxStatus.FAILED
    outbox.encrypted_payload = None


def _sanitize_error(message: str) -> str:
    return message.replace("\r", " ").replace("\n", " ")[:MAX_ERROR_LENGTH]
