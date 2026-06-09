from datetime import datetime

from pydantic import BaseModel, Field, HttpUrl


class JobBase(BaseModel):
    title: str = Field(max_length=255)
    company: str | None = Field(default=None, max_length=255)
    description: str
    requirements: str | None = None
    location: str | None = Field(default=None, max_length=255)
    modality: str | None = Field(default=None, max_length=50)
    salary_min: float | None = Field(default=None, ge=0)
    salary_max: float | None = Field(default=None, ge=0)
    salary_currency: str | None = Field(default=None, max_length=10)
    contract_type: str | None = Field(default=None, max_length=100)
    published_at: datetime | None = None
    source: str = "manual"
    external_id: str | None = None
    url: HttpUrl | None = None


class JobCreate(JobBase):
    pass


class JobRead(JobBase):
    id: int
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class JobRecommendationRead(BaseModel):
    job: JobRead
    final_score: float
    rules_score: float
    semantic_score: float
    matching_skills: list[str]
    missing_skills: list[str]
    score_breakdown: dict | None = None


class JobRecommendationPage(BaseModel):
    items: list[JobRecommendationRead]
    total: int
    limit: int
    offset: int
    has_more: bool


class JobSearchTaskRead(BaseModel):
    task_id: str
    status: str
    message: str
    sources: dict | None = None
    imported: int = 0
    updated: int = 0
    skipped: int = 0
    error: str | None = None

    model_config = {"from_attributes": True}
