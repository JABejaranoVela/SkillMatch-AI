from email.utils import parseaddr
from typing import Literal
from urllib.parse import urlsplit

from cryptography.fernet import Fernet
from email_validator import EmailNotValidError, validate_email
from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    PROJECT_NAME: str = "SkillMatch AI"
    PROJECT_VERSION: str = "0.1.0"
    API_V1_PREFIX: str = "/api/v1"
    ENVIRONMENT: Literal["development", "test", "production"] = "development"

    DATABASE_URL: str = Field(
        default="postgresql+psycopg://skillmatch:skillmatch@localhost:5432/skillmatch"
    )
    SECRET_KEY: str = "change-me-in-production"
    BACKEND_CORS_ORIGINS: list[str] = ["http://localhost:4200"]
    TRUST_PROXY_HEADERS: bool = False
    SESSION_DAYS: int = Field(default=30, ge=1, le=365)
    SESSION_COOKIE_NAME: str = "skillmatch_session"
    COOKIE_SECURE: bool = False
    COOKIE_SAMESITE: Literal["lax", "strict", "none"] = "lax"
    FRONTEND_URL: str = "http://localhost:4200"
    EMAIL_PROVIDER: Literal["console", "brevo", "fake"] = "console"
    EMAIL_FROM: str = "SkillMatch AI <noreply@example.com>"
    BREVO_API_KEY: SecretStr | None = None
    BREVO_API_URL: str = "https://api.brevo.com/v3/smtp/email"
    EMAIL_PAYLOAD_ENCRYPTION_KEY: SecretStr = SecretStr(
        "7NIkUe_WSF1YHO6QkZNmJjj03kT7S6KZETPBeAaT6cQ="
    )
    EMAIL_WORKER_POLL_SECONDS: float = Field(default=2.0, ge=0.1, le=60.0)
    EMAIL_WORKER_BATCH_SIZE: int = Field(default=10, ge=1, le=100)
    EMAIL_WORKER_STALE_MINUTES: int = Field(default=15, ge=1, le=1440)
    EMAIL_MAX_ATTEMPTS: int = Field(default=6, ge=1, le=6)
    EMAIL_HTTP_TIMEOUT_SECONDS: float = Field(default=15.0, ge=1.0, le=120.0)
    PASSWORD_RESET_TTL_MINUTES: int = Field(default=60, ge=10, le=1440)
    PASSWORD_RESET_MAX_REQUESTS_PER_HOUR: int = Field(default=5, ge=1, le=20)
    LOGIN_RATE_LIMIT_ATTEMPTS: int = Field(default=10, ge=1, le=100)
    LOGIN_RATE_LIMIT_WINDOW_MINUTES: int = Field(default=15, ge=1, le=1440)
    REGISTER_RATE_LIMIT_PER_HOUR: int = Field(default=5, ge=1, le=100)
    RESEND_RATE_LIMIT_PER_HOUR: int = Field(default=5, ge=1, le=100)
    FORGOT_PASSWORD_IP_RATE_LIMIT_PER_HOUR: int = Field(default=20, ge=1, le=200)
    RESET_PASSWORD_RATE_LIMIT_PER_HOUR: int = Field(default=10, ge=1, le=100)
    CHANGE_PASSWORD_RATE_LIMIT_PER_HOUR: int = Field(default=5, ge=1, le=100)
    CLEANUP_SESSION_RETENTION_DAYS: int = Field(default=30, ge=1, le=3650)
    CLEANUP_TOKEN_RETENTION_DAYS: int = Field(default=7, ge=1, le=3650)
    CLEANUP_OUTBOX_RETENTION_DAYS: int = Field(default=30, ge=1, le=3650)

    UPLOAD_DIR: str = "storage/resumes"
    SKILLS_DICTIONARY_PATH: str = "data/skills/skills.es.json"
    MAX_UPLOAD_SIZE_MB: int = 10
    ALLOWED_RESUME_EXTENSIONS: set[str] = {".pdf", ".docx"}
    MATCHING_ALGORITHM_VERSION: str = "hybrid-rules-semantic-v1"
    EMBEDDINGS_MODEL_NAME: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    EMBEDDINGS_ENABLED: bool = True
    SKILL_NER_ENABLED: bool = False
    SKILL_NER_MODEL_NAME: str = "urchade/gliner_medium-v2.1"
    TECNOEMPLEO_BASE_URL: str = "https://www.tecnoempleo.com"
    INFOJOBS_API_URL: str = "https://api.infojobs.net/api/1/offer"
    INFOJOBS_CLIENT_ID: str | None = None
    INFOJOBS_CLIENT_SECRET: str | None = None
    PROFILE_JOB_IMPORT_LIMIT: int = 12
    RECOMMENDATIONS_LIMIT: int = 50

    @model_validator(mode="after")
    def validate_security_settings(self) -> "Settings":
        frontend_origin = _normalize_origin(self.FRONTEND_URL)
        cors_origins = {_normalize_origin(origin) for origin in self.BACKEND_CORS_ORIGINS}
        encryption_key = self.EMAIL_PAYLOAD_ENCRYPTION_KEY.get_secret_value().strip()
        try:
            Fernet(encryption_key.encode())
        except (TypeError, ValueError) as exc:
            raise ValueError(
                "EMAIL_PAYLOAD_ENCRYPTION_KEY debe ser una clave Fernet valida"
            ) from exc
        if self.COOKIE_SAMESITE == "none" and not self.COOKIE_SECURE:
            raise ValueError("COOKIE_SECURE debe estar activo cuando COOKIE_SAMESITE=none")
        if self.EMAIL_MAX_ATTEMPTS > 6:
            raise ValueError("EMAIL_MAX_ATTEMPTS no puede superar el intento inicial y 5 reintentos")
        if self.ENVIRONMENT == "production":
            if self.SECRET_KEY == "change-me-in-production" or len(self.SECRET_KEY) < 32:
                raise ValueError("SECRET_KEY debe ser segura en produccion")
            if self.DATABASE_URL == (
                "postgresql+psycopg://skillmatch:skillmatch@localhost:5432/skillmatch"
            ) or "skillmatch:skillmatch@" in self.DATABASE_URL:
                raise ValueError("DATABASE_URL no puede usar credenciales predeterminadas")
            if not self.DATABASE_URL.startswith(
                ("postgresql://", "postgresql+psycopg://")
            ):
                raise ValueError("DATABASE_URL debe usar PostgreSQL en produccion")
            if not self.COOKIE_SECURE:
                raise ValueError("COOKIE_SECURE debe estar activo en produccion")
            if self.COOKIE_SAMESITE != "lax":
                raise ValueError("COOKIE_SAMESITE debe ser lax en produccion")
            if frontend_origin not in cors_origins:
                raise ValueError("BACKEND_CORS_ORIGINS debe incluir FRONTEND_URL")
            for origin in cors_origins:
                parsed_origin = urlsplit(origin)
                if (
                    "*" in origin
                    or parsed_origin.scheme != "https"
                    or parsed_origin.hostname in {"localhost", "127.0.0.1", "::1"}
                ):
                    raise ValueError(
                        "BACKEND_CORS_ORIGINS solo admite origenes HTTPS no locales "
                        "en produccion"
                    )
            brevo_api_key = (
                self.BREVO_API_KEY.get_secret_value().strip()
                if self.BREVO_API_KEY
                else ""
            )
            if self.EMAIL_PROVIDER == "brevo" and not brevo_api_key:
                raise ValueError("BREVO_API_KEY es obligatoria con EMAIL_PROVIDER=brevo")
            if self.EMAIL_PROVIDER != "brevo":
                raise ValueError("EMAIL_PROVIDER debe ser brevo en produccion")
            _validate_production_sender(self.EMAIL_FROM)
            if (
                not encryption_key
                or encryption_key
                == "7NIkUe_WSF1YHO6QkZNmJjj03kT7S6KZETPBeAaT6cQ="
            ):
                raise ValueError(
                    "EMAIL_PAYLOAD_ENCRYPTION_KEY debe ser unica en produccion"
                )
        return self


def _normalize_origin(value: str) -> str:
    parsed = urlsplit(value.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("Los origenes deben ser URLs HTTP(S) validas")
    if parsed.path not in {"", "/"} or parsed.query or parsed.fragment:
        raise ValueError("Los origenes no pueden incluir ruta, query ni fragmento")
    return f"{parsed.scheme.lower()}://{parsed.netloc.lower()}"


def _validate_production_sender(value: str) -> None:
    _sender_name, sender_email = parseaddr(value)
    try:
        validated = validate_email(sender_email, check_deliverability=False)
    except EmailNotValidError as exc:
        raise ValueError("EMAIL_FROM debe contener un email valido") from exc
    domain = validated.domain.lower()
    if domain == "example.com" or domain.endswith(".example.com"):
        raise ValueError("EMAIL_FROM no puede usar example.com en produccion")


settings = Settings()
