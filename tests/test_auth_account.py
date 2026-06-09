from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.api.v1.endpoints.auth import change_password, update_me
from app.core.security import hash_password, verify_password
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
