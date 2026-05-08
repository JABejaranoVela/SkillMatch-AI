from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    PROJECT_NAME: str = "SkillMatch AI"
    PROJECT_VERSION: str = "0.1.0"
    API_V1_PREFIX: str = "/api/v1"

    DATABASE_URL: str = Field(
        default="postgresql+psycopg://skillmatch:skillmatch@localhost:5432/skillmatch"
    )
    SECRET_KEY: str = "change-me-in-production"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    BACKEND_CORS_ORIGINS: list[str] = ["http://localhost:4200"]

    UPLOAD_DIR: str = "storage/resumes"
    SKILLS_DICTIONARY_PATH: str = "data/skills/skills.es.json"
    MAX_UPLOAD_SIZE_MB: int = 10
    ALLOWED_RESUME_EXTENSIONS: set[str] = {".pdf", ".docx"}
    MATCHING_ALGORITHM_VERSION: str = "hybrid-rules-semantic-v1"
    EMBEDDINGS_MODEL_NAME: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    EMBEDDINGS_ENABLED: bool = True
    REMOTIVE_API_URL: str = "https://remotive.com/api/remote-jobs"
    REMOTIVE_DEFAULT_SEARCH: str = "python"
    REMOTIVE_IMPORT_LIMIT: int = 25
    ARBEITNOW_API_URL: str = "https://www.arbeitnow.com/api/job-board-api"
    TECNOEMPLEO_BASE_URL: str = "https://www.tecnoempleo.com"
    PROFILE_JOB_IMPORT_LIMIT: int = 12


settings = Settings()
