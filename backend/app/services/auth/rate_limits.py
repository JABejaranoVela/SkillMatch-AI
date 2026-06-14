from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import math

from fastapi import Request
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.auth import AuthRateLimitBucket


@dataclass(frozen=True)
class RateLimitResult:
    allowed: bool
    retry_after: int
    count: int


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def client_ip_identifier(request: Request) -> str:
    if settings.TRUST_PROXY_HEADERS:
        forwarded_for = request.headers.get("x-forwarded-for", "")
        first_forwarded = forwarded_for.split(",", 1)[0].strip()
        if first_forwarded:
            return first_forwarded
    return request.client.host if request.client else "unknown"


def consume_rate_limit(
    *,
    action: str,
    identifiers: Sequence[str],
    limit: int,
    window_seconds: int,
    now: datetime | None = None,
    session_factory: Callable[[], Session] | None = None,
) -> RateLimitResult:
    current_time = now or utc_now()
    window_epoch = int(current_time.timestamp()) // window_seconds * window_seconds
    window_start = datetime.fromtimestamp(window_epoch, tz=timezone.utc)
    expires_at = window_start + timedelta(seconds=window_seconds)
    key_hash = _bucket_key(action, window_epoch, identifiers)
    statement = (
        insert(AuthRateLimitBucket)
        .values(
            key_hash=key_hash,
            action=action,
            request_count=1,
            window_started_at=window_start,
            expires_at=expires_at,
            created_at=current_time,
            updated_at=current_time,
        )
        .on_conflict_do_update(
            index_elements=[AuthRateLimitBucket.key_hash],
            set_={
                "request_count": AuthRateLimitBucket.request_count + 1,
                "updated_at": current_time,
            },
        )
        .returning(AuthRateLimitBucket.request_count)
    )
    factory = session_factory or SessionLocal
    with factory() as db:
        count = int(db.scalar(statement) or 1)
        db.commit()
    retry_after = max(1, math.ceil((expires_at - current_time).total_seconds()))
    return RateLimitResult(
        allowed=count <= limit,
        retry_after=retry_after,
        count=count,
    )


def _bucket_key(action: str, window_epoch: int, identifiers: Sequence[str]) -> str:
    normalized = "\x1f".join(
        [action.strip().lower(), str(window_epoch)]
        + [str(value).strip().lower() for value in identifiers]
    )
    return hmac.new(
        settings.SECRET_KEY.encode(),
        normalized.encode(),
        hashlib.sha256,
    ).hexdigest()
