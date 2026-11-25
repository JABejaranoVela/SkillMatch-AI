from base64 import urlsafe_b64decode
from hashlib import sha256
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from app.models.user import User
from app.services.auth.account_tokens import (
    create_email_verification_token,
    create_password_reset_token,
    find_email_verification_token,
    find_password_reset_token,
)
from backend_test_database import verified_test_engine


@pytest.fixture
def token_db():
    try:
        engine = verified_test_engine()
    except ValueError as exc:
        pytest.fail(str(exc), pytrace=False)
    try:
        with Session(engine) as db:
            yield db
    finally:
        engine.dispose()


@pytest.mark.parametrize(
    ("issue_token", "find_token", "find_other_purpose"),
    [
        (
            create_email_verification_token,
            find_email_verification_token,
            find_password_reset_token,
        ),
        (
            create_password_reset_token,
            find_password_reset_token,
            find_email_verification_token,
        ),
    ],
    ids=["email-verification", "password-reset"],
)
def test_account_token_digest_is_purpose_bound(
    token_db, issue_token, find_token, find_other_purpose
) -> None:
    user = User(email=f"{uuid4().hex}@example.invalid", hashed_password="unused")
    token_db.add(user)
    token_db.flush()
    token, raw_token = issue_token(token_db, user.id)
    token_db.flush()

    assert len(urlsafe_b64decode(raw_token)) == 48
    assert token.token_hash == sha256(raw_token.encode()).hexdigest()
    assert find_token(token_db, raw_token) is token
    assert find_token(token_db, raw_token + "A") is None
    assert find_token(token_db, token.token_hash) is None
    assert find_other_purpose(token_db, raw_token) is None
