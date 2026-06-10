from types import SimpleNamespace

import bcrypt
import pytest
from fastapi import HTTPException

from app.api.v1.endpoints.auth import change_password, update_me
from app.core.security import (
    hash_password,
    password_needs_rehash,
    verify_password,
    verify_password_and_update,
)
from app.schemas.auth import PasswordChange, UserUpdate


class AccountSession:
    def __init__(self) -> None:
        self.commits = 0
        self.refreshes = 0

    def commit(self) -> None:
        self.commits += 1

    def refresh(self, _item) -> None:
        self.refreshes += 1


def test_update_me_normalizes_name() -> None:
    db = AccountSession()
    user = SimpleNamespace(full_name="Nombre anterior")

    result = update_me(
        payload=UserUpdate(full_name="  Jose Antonio  "),
        db=db,
        current_user=user,
    )

    assert result.full_name == "Jose Antonio"
    assert db.commits == 1
    assert db.refreshes == 1


def test_change_password_rejects_wrong_current_password(monkeypatch) -> None:
    db = AccountSession()
    user = SimpleNamespace(id=1, hashed_password=hash_password("actual123"))
    session = SimpleNamespace(id=9)
    monkeypatch.setattr(
        "app.api.v1.endpoints.auth.invalidate_account_tokens",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        "app.api.v1.endpoints.auth.revoke_user_sessions",
        lambda *_args, **_kwargs: 0,
    )

    with pytest.raises(HTTPException) as exc_info:
        change_password(
            payload=PasswordChange(
                current_password="incorrecta",
                new_password="nueva-segura-1234",
                confirm_password="nueva-segura-1234",
            ),
            db=db,
            current_user=user,
            current_session=session,
        )

    assert exc_info.value.status_code == 400
    assert db.commits == 0


def test_change_password_hashes_new_password_and_keeps_current_session(
    monkeypatch,
) -> None:
    db = AccountSession()
    user = SimpleNamespace(
        id=1,
        hashed_password=hash_password("actual123"),
        password_changed_at=None,
    )
    session = SimpleNamespace(id=9)
    revoked = {}
    monkeypatch.setattr(
        "app.api.v1.endpoints.auth.invalidate_account_tokens",
        lambda *_args, **_kwargs: None,
    )

    def capture_revocation(_db, user_id, *, now, except_session_id):
        revoked.update(
            user_id=user_id,
            now=now,
            except_session_id=except_session_id,
        )
        return 2

    monkeypatch.setattr(
        "app.api.v1.endpoints.auth.revoke_user_sessions",
        capture_revocation,
    )

    response = change_password(
        payload=PasswordChange(
            current_password="actual123",
            new_password="nueva-segura-1234",
            confirm_password="nueva-segura-1234",
        ),
        db=db,
        current_user=user,
        current_session=session,
    )

    assert response.message == "Contrasena actualizada correctamente"
    assert verify_password("nueva-segura-1234", user.hashed_password)
    assert user.password_changed_at is not None
    assert revoked["except_session_id"] == session.id
    assert db.commits == 1


def test_change_password_rejects_reused_password(monkeypatch) -> None:
    db = AccountSession()
    user = SimpleNamespace(id=1, hashed_password=hash_password("actual-segura"))
    session = SimpleNamespace(id=9)
    monkeypatch.setattr(
        "app.api.v1.endpoints.auth.invalidate_account_tokens",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        "app.api.v1.endpoints.auth.revoke_user_sessions",
        lambda *_args, **_kwargs: 0,
    )

    with pytest.raises(HTTPException) as exc_info:
        change_password(
            payload=PasswordChange(
                current_password="actual-segura",
                new_password="actual-segura",
                confirm_password="actual-segura",
            ),
            db=db,
            current_user=user,
            current_session=session,
        )

    assert exc_info.value.status_code == 400
    assert db.commits == 0


def test_new_passwords_use_argon2id() -> None:
    hashed_password = hash_password("Password1234")

    assert hashed_password.startswith("$argon2id$")
    assert verify_password("Password1234", hashed_password)
    assert not password_needs_rehash(hashed_password)


def test_legacy_bcrypt_passwords_remain_valid_and_offer_upgrade() -> None:
    legacy_hash = bcrypt.hashpw(b"Password1234", bcrypt.gensalt()).decode()

    verified, upgraded_hash = verify_password_and_update("Password1234", legacy_hash)

    assert verified is True
    assert upgraded_hash is not None
    assert upgraded_hash.startswith("$argon2id$")
    assert verify_password("Password1234", upgraded_hash)


def test_invalid_password_does_not_offer_hash_upgrade() -> None:
    legacy_hash = bcrypt.hashpw(b"Password1234", bcrypt.gensalt()).decode()

    verified, upgraded_hash = verify_password_and_update("incorrecta", legacy_hash)

    assert verified is False
    assert upgraded_hash is None
