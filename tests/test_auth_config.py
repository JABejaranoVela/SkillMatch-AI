import pytest
from pydantic import SecretStr
from pydantic import ValidationError

from app.core.config import Settings


def secure_production_settings(**overrides):
    values = {
        "_env_file": None,
        "ENVIRONMENT": "production",
        "DATABASE_URL": (
            "postgresql+psycopg://skillmatch_app:strong-password@db:5432/skillmatch"
        ),
        "SECRET_KEY": "a-secure-production-secret-with-more-than-32-characters",
        "COOKIE_SECURE": True,
        "COOKIE_SAMESITE": "lax",
        "FRONTEND_URL": "https://app.skillmatch.example",
        "BACKEND_CORS_ORIGINS": ["https://app.skillmatch.example"],
        "EMAIL_PROVIDER": "brevo",
        "BREVO_API_KEY": "brevo-test-key",
        "EMAIL_FROM": "SkillMatch AI <noreply@skillmatch.example>",
        "EMAIL_PAYLOAD_ENCRYPTION_KEY": (
            "VVHWBaZ4O-F3O_MKPOPbtRm0T44ay8fjkfFKyhVX04c="
        ),
    }
    values.update(overrides)
    return Settings(**values)


def test_samesite_none_requires_secure_cookie() -> None:
    with pytest.raises(ValidationError, match="COOKIE_SECURE"):
        Settings(
            _env_file=None,
            COOKIE_SAMESITE="none",
            COOKIE_SECURE=False,
        )


def test_production_rejects_insecure_defaults() -> None:
    with pytest.raises(ValidationError, match="SECRET_KEY"):
        Settings(
            _env_file=None,
            ENVIRONMENT="production",
        )


def test_production_brevo_requires_api_key() -> None:
    with pytest.raises(ValidationError, match="BREVO_API_KEY"):
        Settings(
            _env_file=None,
            ENVIRONMENT="production",
            SECRET_KEY="a-secure-production-secret-with-more-than-32-characters",
            COOKIE_SECURE=True,
            EMAIL_PROVIDER="brevo",
            BREVO_API_KEY="",
        )


def test_production_accepts_secure_brevo_configuration() -> None:
    settings = secure_production_settings()

    assert settings.COOKIE_SECURE is True
    assert settings.BREVO_API_KEY is not None
    assert settings.BREVO_API_KEY.get_secret_value() == "brevo-test-key"


def test_invalid_email_payload_encryption_key_is_rejected() -> None:
    with pytest.raises(ValidationError, match="Fernet"):
        Settings(
            _env_file=None,
            EMAIL_PAYLOAD_ENCRYPTION_KEY=SecretStr("not-a-fernet-key"),
        )


def test_production_rejects_default_email_payload_key() -> None:
    with pytest.raises(ValidationError, match="EMAIL_PAYLOAD_ENCRYPTION_KEY"):
        secure_production_settings(
            EMAIL_PAYLOAD_ENCRYPTION_KEY=(
                "7NIkUe_WSF1YHO6QkZNmJjj03kT7S6KZETPBeAaT6cQ="
            ),
        )


@pytest.mark.parametrize(
    "overrides",
    [
        {"BACKEND_CORS_ORIGINS": ["*"]},
        {"BACKEND_CORS_ORIGINS": ["https://*.skillmatch.example"]},
        {"BACKEND_CORS_ORIGINS": ["http://app.skillmatch.example"]},
        {"BACKEND_CORS_ORIGINS": ["https://other.skillmatch.example"]},
        {"FRONTEND_URL": "https://localhost"},
    ],
)
def test_production_rejects_unsafe_cors(overrides) -> None:
    with pytest.raises(ValidationError, match="CORS|FRONTEND_URL|HTTPS|origenes"):
        secure_production_settings(**overrides)


def test_production_rejects_default_database_credentials() -> None:
    with pytest.raises(ValidationError, match="DATABASE_URL"):
        secure_production_settings(
            DATABASE_URL=(
                "postgresql+psycopg://skillmatch:skillmatch@db:5432/skillmatch"
            )
        )


def test_production_requires_postgresql() -> None:
    with pytest.raises(ValidationError, match="PostgreSQL"):
        secure_production_settings(
            DATABASE_URL="sqlite:///skillmatch.db"
        )


def test_production_rejects_example_sender() -> None:
    with pytest.raises(ValidationError, match="EMAIL_FROM"):
        secure_production_settings(
            EMAIL_FROM="SkillMatch AI <noreply@example.com>"
        )
