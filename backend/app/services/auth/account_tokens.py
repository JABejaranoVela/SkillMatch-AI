from datetime import datetime, timedelta, timezone
from hashlib import sha256
import hmac
import secrets

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.auth import AccountToken, AccountTokenPurpose

EMAIL_VERIFICATION_TTL = timedelta(hours=24)
RESEND_COOLDOWN = timedelta(seconds=60)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def generate_account_token() -> str:
    return secrets.token_urlsafe(48)


def hash_account_token(token: str) -> str:
    return sha256(token.encode()).hexdigest()


def create_email_verification_token(
    db: Session,
    user_id: int,
    *,
    now: datetime | None = None,
    invalidate_previous: bool = False,
) -> tuple[AccountToken, str]:
    current_time = now or utc_now()
    if invalidate_previous:
        previous_tokens = db.scalars(
            select(AccountToken).where(
                AccountToken.user_id == user_id,
                AccountToken.purpose == AccountTokenPurpose.EMAIL_VERIFICATION,
                AccountToken.used_at.is_(None),
            )
        ).all()
        for previous_token in previous_tokens:
            previous_token.used_at = current_time

    raw_token = generate_account_token()
    account_token = AccountToken(
        user_id=user_id,
        purpose=AccountTokenPurpose.EMAIL_VERIFICATION,
        token_hash=hash_account_token(raw_token),
        expires_at=current_time + EMAIL_VERIFICATION_TTL,
        created_at=current_time,
    )
    db.add(account_token)
    return account_token, raw_token


def create_password_reset_token(
    db: Session,
    user_id: int,
    *,
    now: datetime | None = None,
) -> tuple[AccountToken, str]:
    current_time = now or utc_now()
    invalidate_account_tokens(
        db,
        user_id,
        AccountTokenPurpose.PASSWORD_RESET,
        now=current_time,
    )
    raw_token = generate_account_token()
    account_token = AccountToken(
        user_id=user_id,
        purpose=AccountTokenPurpose.PASSWORD_RESET,
        token_hash=hash_account_token(raw_token),
        expires_at=current_time
        + timedelta(minutes=settings.PASSWORD_RESET_TTL_MINUTES),
        created_at=current_time,
    )
    db.add(account_token)
    return account_token, raw_token


def find_email_verification_token(
    db: Session,
    raw_token: str,
) -> AccountToken | None:
    expected_hash = hash_account_token(raw_token)
    account_token = db.scalar(
        select(AccountToken)
        .where(
            AccountToken.token_hash == expected_hash,
            AccountToken.purpose == AccountTokenPurpose.EMAIL_VERIFICATION,
        )
        .with_for_update()
    )
    if account_token is None:
        return None
    if not hmac.compare_digest(account_token.token_hash, expected_hash):
        return None
    return account_token


def find_password_reset_token(
    db: Session,
    raw_token: str,
) -> AccountToken | None:
    return find_account_token(
        db,
        raw_token,
        AccountTokenPurpose.PASSWORD_RESET,
    )


def find_account_token(
    db: Session,
    raw_token: str,
    purpose: AccountTokenPurpose,
) -> AccountToken | None:
    expected_hash = hash_account_token(raw_token)
    account_token = db.scalar(
        select(AccountToken)
        .where(
            AccountToken.token_hash == expected_hash,
            AccountToken.purpose == purpose,
        )
        .with_for_update()
    )
    if account_token is None:
        return None
    if not hmac.compare_digest(account_token.token_hash, expected_hash):
        return None
    return account_token


def invalidate_account_tokens(
    db: Session,
    user_id: int,
    purpose: AccountTokenPurpose,
    *,
    now: datetime | None = None,
    exclude_token_id: int | None = None,
) -> None:
    current_time = now or utc_now()
    statement = select(AccountToken).where(
        AccountToken.user_id == user_id,
        AccountToken.purpose == purpose,
        AccountToken.used_at.is_(None),
    )
    if exclude_token_id is not None:
        statement = statement.where(AccountToken.id != exclude_token_id)
    for account_token in db.scalars(statement).all():
        account_token.used_at = current_time


def password_reset_request_allowed(
    db: Session,
    user_id: int,
    *,
    now: datetime | None = None,
) -> bool:
    current_time = now or utc_now()
    attempts = db.scalar(
        select(func.count(AccountToken.id)).where(
            AccountToken.user_id == user_id,
            AccountToken.purpose == AccountTokenPurpose.PASSWORD_RESET,
            AccountToken.created_at >= current_time - timedelta(hours=1),
        )
    )
    return int(attempts or 0) < settings.PASSWORD_RESET_MAX_REQUESTS_PER_HOUR


def is_token_expired(
    account_token: AccountToken,
    now: datetime | None = None,
) -> bool:
    current_time = now or utc_now()
    expires_at = account_token.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    return expires_at <= current_time


def seconds_until_resend_allowed(
    db: Session,
    user_id: int,
    *,
    now: datetime | None = None,
) -> int:
    latest_token = db.scalar(
        select(AccountToken)
        .where(
            AccountToken.user_id == user_id,
            AccountToken.purpose == AccountTokenPurpose.EMAIL_VERIFICATION,
        )
        .order_by(AccountToken.created_at.desc())
        .limit(1)
    )
    if latest_token is None:
        return 0

    current_time = now or utc_now()
    created_at = latest_token.created_at
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    remaining = RESEND_COOLDOWN - (current_time - created_at)
    return max(0, int(remaining.total_seconds()) + (1 if remaining.microseconds else 0))
