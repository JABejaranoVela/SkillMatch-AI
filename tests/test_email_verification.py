from datetime import timedelta
from types import SimpleNamespace

import pytest
from fastapi import HTTPException, Request, Response

from app.api.v1.endpoints import auth
from app.models.auth import AccountTokenPurpose
from app.models.user import UserStatus
from app.schemas.auth import UserCreate, VerifyEmailRequest
from app.services.auth.account_tokens import (
    EMAIL_VERIFICATION_TTL,
    create_email_verification_token,
    find_email_verification_token,
    generate_account_token,
    hash_account_token,
    is_token_expired,
    seconds_until_resend_allowed,
    utc_now,
)
from app.services.email.crypto import EmailPayloadCipher
from app.services.email.templates import build_verification_url


class FakeResult:
    def __init__(self, items) -> None:
        self.items = items

    def all(self):
        return self.items


class TokenSession:
    def __init__(self, scalar_value=None, scalar_values=None) -> None:
        self.scalar_value = scalar_value
        self.scalar_values = scalar_values or []
        self.added = []
        self.commits = 0
        self.refreshed = []

    def scalar(self, _statement):
        return self.scalar_value

    def scalars(self, _statement):
        return FakeResult(self.scalar_values)

    def add(self, item) -> None:
        if getattr(item, "id", None) is None:
            item.id = len(self.added) + 1
        self.added.append(item)

    def flush(self) -> None:
        for item in self.added:
            if getattr(item, "id", None) is None:
                item.id = 1

    def commit(self) -> None:
        self.commits += 1

    def refresh(self, item) -> None:
        self.refreshed.append(item)


def make_request(path: str) -> Request:
    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": path,
            "headers": [],
            "client": ("127.0.0.1", 50000),
        }
    )


@pytest.fixture(autouse=True)
def allow_rate_limits(monkeypatch) -> None:
    monkeypatch.setattr(
        auth,
        "consume_rate_limit",
        lambda **_kwargs: SimpleNamespace(allowed=True, retry_after=0),
    )


def make_user(status: UserStatus = UserStatus.PENDING):
    return SimpleNamespace(
        id=1,
        email="pending@example.com",
        full_name="Pending User",
        status=status,
        email_verified_at=utc_now() if status == UserStatus.ACTIVE else None,
    )


def make_pending_user():
    return make_user()


def make_account_token(*, used=False, expired=False, status=UserStatus.PENDING):
    now = utc_now()
    return SimpleNamespace(
        user=make_user(status),
        used_at=now if used else None,
        expires_at=now - timedelta(seconds=1) if expired else now + timedelta(hours=1),
    )


def test_account_token_is_random_hashed_and_expires_in_24_hours() -> None:
    now = utc_now()
    db = TokenSession()

    token, raw_token = create_email_verification_token(db, 7, now=now)

    assert token.purpose == AccountTokenPurpose.EMAIL_VERIFICATION
    assert token.token_hash == hash_account_token(raw_token)
    assert raw_token not in token.token_hash
    assert token.expires_at == now + EMAIL_VERIFICATION_TTL
    assert generate_account_token() != generate_account_token()


def test_token_hash_is_compared_before_returning_match() -> None:
    stored_token = SimpleNamespace(token_hash=hash_account_token("another-token"))
    db = TokenSession(scalar_value=stored_token)

    assert find_email_verification_token(db, "raw-token") is None


def test_resend_invalidates_previous_unused_tokens() -> None:
    now = utc_now()
    previous_token = SimpleNamespace(used_at=None)
    db = TokenSession(scalar_values=[previous_token])

    create_email_verification_token(
        db,
        7,
        now=now,
        invalidate_previous=True,
    )

    assert previous_token.used_at == now


def test_build_verification_url_contains_raw_token_only_for_delivery() -> None:
    url = build_verification_url("raw-token")

    assert url.endswith("/verify-email?token=raw-token")


def test_register_creates_pending_unverified_user() -> None:
    db = TokenSession()

    response = auth.register(
        payload=UserCreate(
            email="new@example.com",
            password="Password1234",
            full_name="New User",
        ),
        request=make_request("/api/v1/auth/register"),
        db=db,
    )

    user = next(item for item in db.added if item.__class__.__name__ == "User")
    assert response.message == auth.REGISTRATION_MESSAGE
    assert user.status == UserStatus.PENDING
    assert user.email_verified_at is None
    assert any(item.__class__.__name__ == "AccountToken" for item in db.added)
    outbox = next(
        item for item in db.added if item.__class__.__name__ == "EmailOutbox"
    )
    assert outbox.status.value == "pending"
    assert "Password1234" not in outbox.encrypted_payload
    payload = EmailPayloadCipher().decrypt(outbox.encrypted_payload)
    assert payload["verification_token"]


def test_register_stores_normalized_email() -> None:
    db = TokenSession()

    auth.register(
        payload=UserCreate(
            email="NEW.User@Example.COM",
            password="Password1234",
            full_name="New User",
        ),
        request=make_request("/api/v1/auth/register"),
        db=db,
    )

    user = next(item for item in db.added if item.__class__.__name__ == "User")
    assert user.email == "new.user@example.com"


def test_register_does_not_reveal_existing_email() -> None:
    existing_user = make_pending_user()
    db = TokenSession(scalar_value=existing_user)

    response = auth.register(
        payload=UserCreate(
            email="PENDING@EXAMPLE.COM",
            password="Password1234",
            full_name="Existing User",
        ),
        request=make_request("/api/v1/auth/register"),
        db=db,
    )

    assert response.message == auth.REGISTRATION_MESSAGE
    assert db.added == []


def test_register_keeps_generic_response_when_rate_limited(monkeypatch) -> None:
    monkeypatch.setattr(
        auth,
        "consume_rate_limit",
        lambda **_kwargs: SimpleNamespace(allowed=False, retry_after=1200),
    )
    db = TokenSession()

    response = auth.register(
        payload=UserCreate(
            email="new@example.com",
            password="Password1234",
            full_name="New User",
        ),
        request=make_request("/api/v1/auth/register"),
        db=db,
    )

    assert response.message == auth.REGISTRATION_MESSAGE
    assert db.added == []


def test_valid_verification_token_activates_user(monkeypatch) -> None:
    db = TokenSession()
    account_token = make_account_token()
    monkeypatch.setattr(auth, "find_email_verification_token", lambda *_: account_token)

    response = auth.verify_email(VerifyEmailRequest(token="x" * 48), db)

    assert response.message == "Correo verificado correctamente"
    assert account_token.user.status == UserStatus.ACTIVE
    assert account_token.user.email_verified_at is not None
    assert account_token.used_at is not None
    assert db.commits == 1


def test_valid_verification_token_is_idempotent_for_active_user(monkeypatch) -> None:
    db = TokenSession()
    account_token = make_account_token(status=UserStatus.ACTIVE)
    verified_at = account_token.user.email_verified_at
    monkeypatch.setattr(auth, "find_email_verification_token", lambda *_: account_token)

    response = auth.verify_email(VerifyEmailRequest(token="x" * 48), db)

    assert response.message == "Correo verificado correctamente"
    assert account_token.user.status == UserStatus.ACTIVE
    assert account_token.user.email_verified_at == verified_at
    assert account_token.used_at is not None
    assert db.commits == 1


def test_valid_verification_token_does_not_reactivate_disabled_user(monkeypatch) -> None:
    db = TokenSession()
    account_token = make_account_token(status=UserStatus.DISABLED)
    monkeypatch.setattr(auth, "find_email_verification_token", lambda *_: account_token)

    with pytest.raises(HTTPException) as exc_info:
        auth.verify_email(VerifyEmailRequest(token="x" * 48), db)

    assert exc_info.value.status_code == 400
    assert account_token.user.status == UserStatus.DISABLED
    assert account_token.user.email_verified_at is None
    assert account_token.used_at is not None
    assert db.commits == 1


def test_expired_verification_token_does_not_activate_user(monkeypatch) -> None:
    account_token = make_account_token(expired=True)
    monkeypatch.setattr(auth, "find_email_verification_token", lambda *_: account_token)

    with pytest.raises(HTTPException) as exc_info:
        auth.verify_email(VerifyEmailRequest(token="x" * 48), TokenSession())

    assert exc_info.value.status_code == 410
    assert account_token.user.status == UserStatus.PENDING


def test_used_verification_token_cannot_be_reused(monkeypatch) -> None:
    account_token = make_account_token(used=True)
    monkeypatch.setattr(auth, "find_email_verification_token", lambda *_: account_token)

    with pytest.raises(HTTPException) as exc_info:
        auth.verify_email(VerifyEmailRequest(token="x" * 48), TokenSession())

    assert exc_info.value.status_code == 409
    assert account_token.user.status == UserStatus.PENDING


def test_tampered_verification_token_fails(monkeypatch) -> None:
    monkeypatch.setattr(auth, "find_email_verification_token", lambda *_: None)

    with pytest.raises(HTTPException) as exc_info:
        auth.verify_email(VerifyEmailRequest(token="tampered-" + "x" * 32), TokenSession())

    assert exc_info.value.status_code == 400


def test_token_expiration_handles_timezone() -> None:
    assert is_token_expired(make_account_token(expired=True))
    assert not is_token_expired(make_account_token())


def test_resend_cooldown_reports_remaining_seconds() -> None:
    now = utc_now()
    latest_token = SimpleNamespace(created_at=now - timedelta(seconds=10))
    db = TokenSession(scalar_value=latest_token)

    remaining = seconds_until_resend_allowed(db, 1, now=now)

    assert 49 <= remaining <= 50


def test_resend_endpoint_rejects_request_during_cooldown(monkeypatch) -> None:
    monkeypatch.setattr(auth, "seconds_until_resend_allowed", lambda *_: 42)

    with pytest.raises(HTTPException) as exc_info:
        auth.resend_verification(
            request=make_request("/api/v1/auth/resend-verification"),
            response=Response(),
            db=TokenSession(),
            current_user=make_pending_user(),
        )

    assert exc_info.value.status_code == 429
    assert exc_info.value.headers["Retry-After"] == "42"


def test_resend_hourly_limit_returns_retry_after(monkeypatch) -> None:
    monkeypatch.setattr(
        auth,
        "consume_rate_limit",
        lambda **_kwargs: SimpleNamespace(allowed=False, retry_after=900),
    )

    with pytest.raises(HTTPException) as exc_info:
        auth.resend_verification(
            request=make_request("/api/v1/auth/resend-verification"),
            response=Response(),
            db=TokenSession(),
            current_user=make_pending_user(),
        )

    assert exc_info.value.status_code == 429
    assert exc_info.value.headers["Retry-After"] == "900"
