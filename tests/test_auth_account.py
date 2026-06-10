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


def test_change_password_rejects_wrong_current_password() -> None:
    db = AccountSession()
    user = SimpleNamespace(hashed_password=hash_password("actual123"))

    with pytest.raises(HTTPException) as exc_info:
        change_password(
            payload=PasswordChange(
                current_password="incorrecta",
                new_password="nueva1234",
            ),
            db=db,
            current_user=user,
        )

    assert exc_info.value.status_code == 400
    assert db.commits == 0


def test_change_password_hashes_new_password() -> None:
    db = AccountSession()
    user = SimpleNamespace(hashed_password=hash_password("actual123"))

    change_password(
        payload=PasswordChange(
            current_password="actual123",
            new_password="nueva1234",
        ),
        db=db,
        current_user=user,
    )

    assert verify_password("nueva1234", user.hashed_password)
    assert db.commits == 1


def test_change_password_rejects_reused_password() -> None:
    db = AccountSession()
    user = SimpleNamespace(hashed_password=hash_password("actual123"))

    with pytest.raises(HTTPException) as exc_info:
        change_password(
            payload=PasswordChange(
                current_password="actual123",
                new_password="actual123",
            ),
            db=db,
            current_user=user,
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
