from datetime import timedelta
from types import SimpleNamespace

import bcrypt
import pytest
from fastapi import HTTPException, Request, Response

from app.api.v1.endpoints.auth import login, logout
from app.core.config import settings
from app.core.security import hash_password
from app.models.user import UserRole, UserStatus
from app.services.auth.sessions import (
    clear_session_cookie,
    generate_session_token,
    hash_session_token,
    is_session_active,
    revoke_session,
    set_session_cookie,
    utc_now,
)


class EndpointSession:
    def __init__(self, user=None, previous_session=None) -> None:
        self.user = user
        self.previous_session = previous_session
        self.added = []
        self.commits = 0
        self.scalar_calls = 0

    def scalar(self, _statement):
        self.scalar_calls += 1
        if self.scalar_calls == 1 and self.user is not None:
            return self.user
        return self.previous_session

    def add(self, item) -> None:
        self.added.append(item)

    def commit(self) -> None:
        self.commits += 1

    def refresh(self, _item) -> None:
        return None


def make_request(cookie: str | None = None) -> Request:
    headers = [(b"user-agent", b"pytest")]
    if cookie:
        headers.append(
            (b"cookie", f"{settings.SESSION_COOKIE_NAME}={cookie}".encode())
        )
    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/api/v1/auth/login",
            "headers": headers,
            "client": ("127.0.0.1", 50000),
        }
    )


def make_user(
    password_hash: str,
    status: UserStatus = UserStatus.ACTIVE,
):
    return SimpleNamespace(
        id=1,
        email="user@example.com",
        full_name="User",
        role=UserRole.USER,
        status=status,
        email_verified_at=utc_now(),
        hashed_password=password_hash,
        last_login_at=None,
    )


def test_session_tokens_are_random_and_stored_as_hashes() -> None:
    first_token = generate_session_token()
    second_token = generate_session_token()

    assert first_token != second_token
    assert len(first_token) >= 64
    assert hash_session_token(first_token) != first_token
    assert len(hash_session_token(first_token)) == 64


def test_session_activity_requires_future_expiry_and_no_revocation() -> None:
    now = utc_now()
    active_session = SimpleNamespace(
        expires_at=now + timedelta(minutes=5),
        revoked_at=None,
    )
    expired_session = SimpleNamespace(
        expires_at=now - timedelta(seconds=1),
        revoked_at=None,
    )
    revoked_session = SimpleNamespace(
        expires_at=now + timedelta(minutes=5),
        revoked_at=now,
    )

    assert is_session_active(active_session, now)
    assert not is_session_active(expired_session, now)
    assert not is_session_active(revoked_session, now)


def test_revoke_session_is_idempotent() -> None:
    auth_session = SimpleNamespace(revoked_at=None)
    first_revocation = utc_now()

    revoke_session(auth_session, first_revocation)
    revoke_session(auth_session, first_revocation + timedelta(minutes=1))

    assert auth_session.revoked_at == first_revocation


def test_session_cookie_is_http_only_and_uses_configured_policy() -> None:
    response = Response()

    set_session_cookie(response, "raw-session-token")

    cookie = response.headers["set-cookie"]
    assert f"{settings.SESSION_COOKIE_NAME}=raw-session-token" in cookie
    assert "HttpOnly" in cookie
    assert "Path=/" in cookie
    assert "SameSite=lax" in cookie
    assert f"Max-Age={settings.SESSION_DAYS * 24 * 60 * 60}" in cookie
    assert ("Secure" in cookie) is settings.COOKIE_SECURE


def test_clear_session_cookie_expires_cookie() -> None:
    response = Response()

    clear_session_cookie(response)

    cookie = response.headers["set-cookie"]
    assert f"{settings.SESSION_COOKIE_NAME}=" in cookie
    assert "Max-Age=0" in cookie
    assert "HttpOnly" in cookie


def test_login_creates_hashed_session_and_upgrades_bcrypt() -> None:
    user = make_user(bcrypt.hashpw(b"Password123", bcrypt.gensalt()).decode())
    db = EndpointSession(user=user)
    response = Response()
    form = SimpleNamespace(username=user.email, password="Password123")

    result = login(
        form_data=form,
        db=db,
        request=make_request(),
        response=response,
    )

    assert result is user
    assert user.last_login_at is not None
    assert user.hashed_password.startswith("$argon2id$")
    assert db.commits == 1
    assert len(db.added) == 1
    auth_session = db.added[0]
    cookie = response.headers["set-cookie"]
    raw_token = cookie.split("=", 1)[1].split(";", 1)[0]
    assert auth_session.token_hash == hash_session_token(raw_token)
    assert raw_token not in auth_session.token_hash
    assert auth_session.last_seen_at is not None
    assert auth_session.ip_address == "127.0.0.1"
    assert auth_session.user_agent == "pytest"


def test_login_revokes_previous_cookie_session() -> None:
    previous_session = SimpleNamespace(revoked_at=None)
    user = make_user(hash_password("Password1234"))
    db = EndpointSession(user=user, previous_session=previous_session)
    response = Response()
    form = SimpleNamespace(username=user.email, password="Password1234")

    login(
        form_data=form,
        db=db,
        request=make_request("previous-raw-token"),
        response=response,
    )

    assert previous_session.revoked_at is not None
    assert len(db.added) == 1


def test_pending_user_can_create_session() -> None:
    user = make_user(
        hash_password("Password1234"),
        status=UserStatus.PENDING,
    )
    db = EndpointSession(user=user)

    result = login(
        form_data=SimpleNamespace(
            username=user.email,
            password="Password1234",
        ),
        db=db,
        request=make_request(),
        response=Response(),
    )

    assert result.status == UserStatus.PENDING
    assert len(db.added) == 1


def test_disabled_user_cannot_create_session() -> None:
    user = make_user(
        hash_password("Password1234"),
        status=UserStatus.DISABLED,
    )
    db = EndpointSession(user=user)

    with pytest.raises(HTTPException) as exc_info:
        login(
            form_data=SimpleNamespace(
                username=user.email,
                password="Password1234",
            ),
            db=db,
            request=make_request(),
            response=Response(),
        )

    assert exc_info.value.status_code == 403
    assert db.added == []
    assert db.commits == 0


def test_logout_revokes_session_and_clears_cookie() -> None:
    auth_session = SimpleNamespace(revoked_at=None)
    db = EndpointSession(previous_session=auth_session)
    db.scalar_calls = 1
    response = Response()

    logout(
        request=make_request("raw-token"),
        response=response,
        db=db,
    )

    assert auth_session.revoked_at is not None
    assert db.commits == 1
    cookie = response.headers["set-cookie"]
    assert f"{settings.SESSION_COOKIE_NAME}=" in cookie
    assert "Max-Age=0" in cookie
