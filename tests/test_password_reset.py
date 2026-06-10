from datetime import timedelta
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.api.v1.endpoints import auth
from app.core.config import settings
from app.core.security import hash_password, verify_password
from app.models.auth import AccountTokenPurpose, EmailOutbox
from app.models.user import UserStatus
from app.schemas.auth import ForgotPasswordRequest, ResetPasswordRequest
from app.services.auth.account_tokens import (
    create_password_reset_token,
    hash_account_token,
    password_reset_request_allowed,
    utc_now,
)
from app.services.email.crypto import EmailPayloadCipher


class FakeResult:
    def __init__(self, items) -> None:
        self.items = items

    def all(self):
        return self.items


class PasswordResetSession:
    def __init__(self, scalar_values=None, collection=None) -> None:
        self.scalar_values = list(scalar_values or [])
        self.collection = list(collection or [])
        self.added = []
        self.commits = 0

    def scalar(self, _statement):
        return self.scalar_values.pop(0) if self.scalar_values else None

    def scalars(self, _statement):
        return FakeResult(self.collection)

    def add(self, item) -> None:
        if getattr(item, "id", None) is None:
            item.id = len(self.added) + 1
        self.added.append(item)

    def flush(self) -> None:
        for index, item in enumerate(self.added, start=1):
            if getattr(item, "id", None) is None:
                item.id = index

    def commit(self) -> None:
        self.commits += 1


def active_user():
    return SimpleNamespace(
        id=4,
        email="user@example.com",
        full_name="Test User",
        status=UserStatus.ACTIVE,
        email_verified_at=utc_now(),
        hashed_password=hash_password("old-password-123"),
        password_changed_at=None,
    )


def reset_token(*, used=False, expired=False):
    now = utc_now()
    return SimpleNamespace(
        id=7,
        user=active_user(),
        user_id=4,
        purpose=AccountTokenPurpose.PASSWORD_RESET,
        used_at=now if used else None,
        expires_at=now - timedelta(seconds=1) if expired else now + timedelta(hours=1),
    )


def test_password_reset_token_is_hashed_and_expires_in_60_minutes() -> None:
    now = utc_now()
    db = PasswordResetSession()

    token, raw_token = create_password_reset_token(db, 4, now=now)

    assert token.purpose == AccountTokenPurpose.PASSWORD_RESET
    assert token.token_hash == hash_account_token(raw_token)
    assert raw_token not in token.token_hash
    assert token.expires_at == now + timedelta(
        minutes=settings.PASSWORD_RESET_TTL_MINUTES
    )


def test_password_reset_rate_limit_allows_fewer_than_five() -> None:
    assert password_reset_request_allowed(
        PasswordResetSession(scalar_values=[4]),
        4,
    )
    assert not password_reset_request_allowed(
        PasswordResetSession(scalar_values=[5]),
        4,
    )


@pytest.mark.parametrize(
    "user",
    [
        None,
        SimpleNamespace(status=UserStatus.PENDING),
        SimpleNamespace(status=UserStatus.DISABLED),
    ],
)
def test_forgot_password_always_returns_generic_for_ineligible_user(user) -> None:
    db = PasswordResetSession(scalar_values=[user])

    response = auth.forgot_password(
        ForgotPasswordRequest(email="missing@example.com"),
        db,
    )

    assert response.message == auth.FORGOT_PASSWORD_MESSAGE
    assert db.added == []
    assert db.commits == 0


def test_forgot_password_creates_token_and_encrypted_outbox(monkeypatch) -> None:
    user = active_user()
    db = PasswordResetSession(scalar_values=[user])
    monkeypatch.setattr(auth, "password_reset_request_allowed", lambda *_: True)

    response = auth.forgot_password(
        ForgotPasswordRequest(email="USER@example.com"),
        db,
    )

    assert response.message == auth.FORGOT_PASSWORD_MESSAGE
    token = next(item for item in db.added if item.__class__.__name__ == "AccountToken")
    outbox = next(item for item in db.added if isinstance(item, EmailOutbox))
    assert token.purpose == AccountTokenPurpose.PASSWORD_RESET
    assert outbox.template == "password_reset"
    payload = EmailPayloadCipher().decrypt(outbox.encrypted_payload)
    assert payload["password_reset_token"]
    assert payload["password_reset_token"] not in outbox.encrypted_payload
    assert db.commits == 1


def test_forgot_password_silently_respects_rate_limit(monkeypatch) -> None:
    db = PasswordResetSession(scalar_values=[active_user()])
    monkeypatch.setattr(auth, "password_reset_request_allowed", lambda *_: False)

    response = auth.forgot_password(
        ForgotPasswordRequest(email="user@example.com"),
        db,
    )

    assert response.message == auth.FORGOT_PASSWORD_MESSAGE
    assert db.added == []
    assert db.commits == 0


def test_valid_reset_changes_password_and_revokes_all_sessions(monkeypatch) -> None:
    token = reset_token()
    db = PasswordResetSession()
    revoked = {}
    monkeypatch.setattr(auth, "find_password_reset_token", lambda *_: token)
    monkeypatch.setattr(
        auth,
        "invalidate_account_tokens",
        lambda *_args, **_kwargs: None,
    )

    def capture_revocation(_db, user_id, *, now):
        revoked.update(user_id=user_id, now=now)
        return 3

    monkeypatch.setattr(auth, "revoke_user_sessions", capture_revocation)

    response = auth.reset_password(
        ResetPasswordRequest(
            token="x" * 48,
            new_password="new-password-123",
            confirm_password="new-password-123",
        ),
        db,
    )

    assert response.message == "Contrasena restablecida correctamente"
    assert verify_password("new-password-123", token.user.hashed_password)
    assert token.user.password_changed_at is not None
    assert token.used_at is not None
    assert revoked["user_id"] == token.user.id
    assert db.commits == 1


@pytest.mark.parametrize(
    ("token", "expected_status"),
    [(None, 400), (reset_token(used=True), 409), (reset_token(expired=True), 410)],
)
def test_reset_rejects_invalid_used_or_expired_token(
    monkeypatch,
    token,
    expected_status,
) -> None:
    monkeypatch.setattr(auth, "find_password_reset_token", lambda *_: token)

    with pytest.raises(HTTPException) as exc_info:
        auth.reset_password(
            ResetPasswordRequest(
                token="x" * 48,
                new_password="new-password-123",
                confirm_password="new-password-123",
            ),
            PasswordResetSession(),
        )

    assert exc_info.value.status_code == expected_status
    assert exc_info.value.detail == auth.INVALID_RESET_LINK_MESSAGE


def test_reset_requires_matching_confirmation() -> None:
    with pytest.raises(ValidationError):
        ResetPasswordRequest(
            token="x" * 48,
            new_password="new-password-123",
            confirm_password="different-password",
        )
