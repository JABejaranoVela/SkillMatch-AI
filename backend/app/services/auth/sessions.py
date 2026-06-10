from datetime import datetime, timedelta, timezone
from hashlib import sha256
import secrets

from fastapi import Request, Response
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.core.config import settings
from app.models.auth import AuthSession


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def hash_session_token(token: str) -> str:
    return sha256(token.encode()).hexdigest()


def generate_session_token() -> str:
    return secrets.token_urlsafe(48)


def create_session(
    db: Session,
    user_id: int,
    request: Request,
) -> tuple[AuthSession, str]:
    now = utc_now()
    raw_token = generate_session_token()
    csrf_token = secrets.token_urlsafe(32)
    auth_session = AuthSession(
        user_id=user_id,
        token_hash=hash_session_token(raw_token),
        csrf_hash=hash_session_token(csrf_token),
        expires_at=now + timedelta(days=settings.SESSION_DAYS),
        last_seen_at=now,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        created_at=now,
    )
    db.add(auth_session)
    return auth_session, raw_token


def find_session(db: Session, raw_token: str | None) -> AuthSession | None:
    if not raw_token:
        return None
    return db.scalar(
        select(AuthSession)
        .options(joinedload(AuthSession.user))
        .where(AuthSession.token_hash == hash_session_token(raw_token))
    )


def revoke_session(auth_session: AuthSession, now: datetime | None = None) -> None:
    if auth_session.revoked_at is None:
        auth_session.revoked_at = now or utc_now()


def is_session_active(auth_session: AuthSession, now: datetime | None = None) -> bool:
    current_time = now or utc_now()
    expires_at = auth_session.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    return auth_session.revoked_at is None and expires_at > current_time


def touch_session(
    db: Session,
    auth_session: AuthSession,
    minimum_interval: timedelta = timedelta(minutes=5),
) -> None:
    now = utc_now()
    last_seen_at = auth_session.last_seen_at
    if last_seen_at.tzinfo is None:
        last_seen_at = last_seen_at.replace(tzinfo=timezone.utc)
    if now - last_seen_at >= minimum_interval:
        auth_session.last_seen_at = now
        db.commit()


def set_session_cookie(response: Response, raw_token: str) -> None:
    max_age = int(timedelta(days=settings.SESSION_DAYS).total_seconds())
    response.set_cookie(
        key=settings.SESSION_COOKIE_NAME,
        value=raw_token,
        max_age=max_age,
        expires=utc_now() + timedelta(days=settings.SESSION_DAYS),
        path="/",
        secure=settings.COOKIE_SECURE,
        httponly=True,
        samesite=settings.COOKIE_SAMESITE,
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(
        key=settings.SESSION_COOKIE_NAME,
        path="/",
        secure=settings.COOKIE_SECURE,
        httponly=True,
        samesite=settings.COOKIE_SAMESITE,
    )


def session_token_from_request(request: Request) -> str | None:
    return request.cookies.get(settings.SESSION_COOKIE_NAME)
