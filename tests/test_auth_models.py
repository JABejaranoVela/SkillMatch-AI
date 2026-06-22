from app.models.auth import (
    AccountToken,
    AccountTokenPurpose,
    AuthRateLimitBucket,
    AuthSession,
    EmailOutbox,
    EmailOutboxStatus,
)
from app.models.feedback import UserJobInteraction
from app.models.resume import Resume
from app.models.user import User
from app.models.user import UserStatus


def test_auth_foundation_models_are_registered() -> None:
    assert AuthSession.__tablename__ == "auth_sessions"
    assert AccountToken.__tablename__ == "account_tokens"
    assert EmailOutbox.__tablename__ == "email_outbox"
    assert AuthRateLimitBucket.__tablename__ == "auth_rate_limit_buckets"
    assert "encrypted_payload" in EmailOutbox.__table__.columns
    assert "last_error" in EmailOutbox.__table__.columns
    assert "last_attempt_at" in EmailOutbox.__table__.columns


def test_auth_enums_use_public_lowercase_values() -> None:
    assert UserStatus.PENDING.value == "pending"
    assert UserStatus.ACTIVE.value == "active"
    assert AccountTokenPurpose.EMAIL_VERIFICATION.value == "email_verification"
    assert AccountTokenPurpose.PASSWORD_RESET.value == "password_reset"
    assert EmailOutboxStatus.PENDING.value == "pending"
    assert EmailOutboxStatus.CANCELLED.value == "cancelled"


def test_users_have_case_insensitive_email_unique_index() -> None:
    index = next(
        index
        for index in User.__table__.indexes
        if index.name == "ix_users_email_normalized_unique"
    )

    assert index.unique is True
    expressions = [str(expression) for expression in index.expressions]
    assert expressions == ["lower(btrim(users.email))"]


def test_resumes_have_single_active_resume_index() -> None:
    index = next(
        index
        for index in Resume.__table__.indexes
        if index.name == "uq_resumes_one_active_per_user"
    )

    assert index.unique is True
    assert [column.name for column in index.columns] == ["user_id"]
    assert str(index.dialect_options["postgresql"]["where"]) == (
        "resumes.is_active IS true"
    )


def test_user_job_interactions_index_match_result_id() -> None:
    index = next(
        index
        for index in UserJobInteraction.__table__.indexes
        if index.name == "ix_user_job_interactions_match_result_id"
    )

    assert [column.name for column in index.columns] == ["match_result_id"]
