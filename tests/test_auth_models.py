from app.models.auth import (
    AccountToken,
    AccountTokenPurpose,
    AuthSession,
    EmailOutbox,
    EmailOutboxStatus,
)
from app.models.user import UserStatus


def test_auth_foundation_models_are_registered() -> None:
    assert AuthSession.__tablename__ == "auth_sessions"
    assert AccountToken.__tablename__ == "account_tokens"
    assert EmailOutbox.__tablename__ == "email_outbox"


def test_auth_enums_use_public_lowercase_values() -> None:
    assert UserStatus.PENDING.value == "pending"
    assert UserStatus.ACTIVE.value == "active"
    assert AccountTokenPurpose.EMAIL_VERIFICATION.value == "email_verification"
    assert AccountTokenPurpose.PASSWORD_RESET.value == "password_reset"
    assert EmailOutboxStatus.PENDING.value == "pending"
    assert EmailOutboxStatus.CANCELLED.value == "cancelled"
