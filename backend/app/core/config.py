from typing import Literal

from cryptography.fernet import Fernet
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
    EMAIL_HTTP_TIMEOUT_SECONDS: float = Field(default=15.0, ge=1.0, le=120.0)
    PASSWORD_RESET_TTL_MINUTES: int = Field(default=60, ge=10, le=1440)
    PASSWORD_RESET_MAX_REQUESTS_PER_HOUR: int = Field(default=5, ge=1, le=20)

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
        encryption_key = self.EMAIL_PAYLOAD_ENCRYPTION_KEY.get_secret_value().strip()
        try:
            Fernet(encryption_key.encode())
        except (TypeError, ValueError) as exc:
            raise ValueError(
                "EMAIL_PAYLOAD_ENCRYPTION_KEY debe ser una clave Fernet valida"
            ) from exc
        if self.COOKIE_SAMESITE == "none" and not self.COOKIE_SECURE:
            raise ValueError("COOKIE_SECURE debe estar activo cuando COOKIE_SAMESITE=none")
        if self.ENVIRONMENT == "production":
            if self.SECRET_KEY == "change-me-in-production" or len(self.SECRET_KEY) < 32:
                raise ValueError("SECRET_KEY debe ser segura en produccion")
            if not self.COOKIE_SECURE:
                raise ValueError("COOKIE_SECURE debe estar activo en produccion")
            brevo_api_key = (
                self.BREVO_API_KEY.get_secret_value().strip()
                if self.BREVO_API_KEY
                else ""
            )
            if self.EMAIL_PROVIDER == "brevo" and not brevo_api_key:
                raise ValueError("BREVO_API_KEY es obligatoria con EMAIL_PROVIDER=brevo")
            if self.EMAIL_PROVIDER != "brevo":
                raise ValueError("EMAIL_PROVIDER debe ser brevo en produccion")
            if (
                not encryption_key
                or encryption_key
                == "7NIkUe_WSF1YHO6QkZNmJjj03kT7S6KZETPBeAaT6cQ="
            ):
                raise ValueError(
                    "EMAIL_PAYLOAD_ENCRYPTION_KEY debe ser unica en produccion"
                )
        return self


settings = Settings()
