from datetime import datetime

from pydantic import BaseModel


class ResumeRead(BaseModel):
    id: int
    filename: str
    file_type: str
    status: str
    is_active: bool
    created_at: datetime
    processed_at: datetime | None = None

    model_config = {"from_attributes": True}


class ProfileRead(BaseModel):
    id: int
    profile_type: str | None = None
    summary: str | None = None
    experience_years: float | None = None
    education: dict | None = None
    languages: list | None = None
    technologies: list | None = None
    analysis: dict | None = None

    model_config = {"from_attributes": True}
