import pytest
from pydantic import ValidationError

from app.core.config import Settings


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
    settings = Settings(
        _env_file=None,
        ENVIRONMENT="production",
        SECRET_KEY="a-secure-production-secret-with-more-than-32-characters",
        COOKIE_SECURE=True,
        EMAIL_PROVIDER="brevo",
        BREVO_API_KEY="brevo-test-key",
    )

    assert settings.COOKIE_SECURE is True
    assert settings.BREVO_API_KEY is not None
    assert settings.BREVO_API_KEY.get_secret_value() == "brevo-test-key"
