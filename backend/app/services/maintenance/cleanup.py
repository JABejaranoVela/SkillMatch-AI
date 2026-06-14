from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, func, or_, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.auth import (
    AccountToken,
    AuthRateLimitBucket,
    AuthSession,
    EmailOutbox,
    EmailOutboxStatus,
)
from app.services.email.outbox import (
    cancel_legacy_messages,
    recover_abandoned_messages,
)


@dataclass(frozen=True)
class CleanupResult:
    dry_run: bool
    sessions: int
    account_tokens: int
    email_outbox: int
    rate_limit_buckets: int
    legacy_outbox_cancelled: int
    abandoned_outbox_recovered: int

    def to_dict(self) -> dict[str, bool | int]:
        return asdict(self)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def cleanup_temporary_data(
    db: Session,
    *,
    dry_run: bool = False,
    session_retention_days: int | None = None,
    token_retention_days: int | None = None,
    outbox_retention_days: int | None = None,
    now: datetime | None = None,
) -> CleanupResult:
    current_time = now or utc_now()
    session_cutoff = current_time - timedelta(
        days=session_retention_days or settings.CLEANUP_SESSION_RETENTION_DAYS
    )
    token_cutoff = current_time - timedelta(
        days=token_retention_days or settings.CLEANUP_TOKEN_RETENTION_DAYS
    )
    outbox_cutoff = current_time - timedelta(
        days=outbox_retention_days or settings.CLEANUP_OUTBOX_RETENTION_DAYS
    )

    session_filter = or_(
        AuthSession.expires_at <= session_cutoff,
        AuthSession.revoked_at <= session_cutoff,
    )
    token_filter = or_(
        AccountToken.expires_at <= token_cutoff,
        AccountToken.used_at <= token_cutoff,
    )
    outbox_filter = (
        EmailOutbox.status.in_(
            [
                EmailOutboxStatus.SENT,
                EmailOutboxStatus.CANCELLED,
                EmailOutboxStatus.FAILED,
            ]
        )
        & (EmailOutbox.updated_at <= outbox_cutoff)
    )
    bucket_filter = AuthRateLimitBucket.expires_at <= current_time
    legacy_filter = (
        EmailOutbox.status.in_(
            [EmailOutboxStatus.PENDING, EmailOutboxStatus.SENDING]
        )
        & EmailOutbox.encrypted_payload.is_(None)
    )
    stale_before = current_time - timedelta(
        minutes=settings.EMAIL_WORKER_STALE_MINUTES
    )
    abandoned_filter = (
        (EmailOutbox.status == EmailOutboxStatus.SENDING)
        & EmailOutbox.encrypted_payload.is_not(None)
        & (
            (
                EmailOutbox.last_attempt_at.is_not(None)
                & (EmailOutbox.last_attempt_at <= stale_before)
            )
            | (
                EmailOutbox.last_attempt_at.is_(None)
                & (EmailOutbox.updated_at <= stale_before)
            )
        )
    )

    if dry_run:
        return CleanupResult(
            dry_run=True,
            sessions=_count(db, AuthSession, session_filter),
            account_tokens=_count(db, AccountToken, token_filter),
            email_outbox=_count(db, EmailOutbox, outbox_filter),
            rate_limit_buckets=_count(db, AuthRateLimitBucket, bucket_filter),
            legacy_outbox_cancelled=_count(db, EmailOutbox, legacy_filter),
            abandoned_outbox_recovered=_count(db, EmailOutbox, abandoned_filter),
        )

    legacy_cancelled = cancel_legacy_messages(db, now=current_time)
    abandoned_recovered = recover_abandoned_messages(db, now=current_time)
    sessions = _delete(db, AuthSession, session_filter)
    account_tokens = _delete(db, AccountToken, token_filter)
    email_outbox = _delete(db, EmailOutbox, outbox_filter)
    rate_limit_buckets = _delete(db, AuthRateLimitBucket, bucket_filter)
    db.commit()
    return CleanupResult(
        dry_run=False,
        sessions=sessions,
        account_tokens=account_tokens,
        email_outbox=email_outbox,
        rate_limit_buckets=rate_limit_buckets,
        legacy_outbox_cancelled=legacy_cancelled,
        abandoned_outbox_recovered=abandoned_recovered,
    )


def _count(db: Session, model, condition) -> int:
    statement = select(func.count()).select_from(model).where(condition)
    return int(db.scalar(statement) or 0)


def _delete(db: Session, model, condition) -> int:
    result = db.execute(delete(model).where(condition))
    return int(result.rowcount or 0)
