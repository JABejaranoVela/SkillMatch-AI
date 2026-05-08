from pydantic import BaseModel, Field, HttpUrl


class JobBase(BaseModel):
    title: str = Field(max_length=255)
    company: str | None = Field(default=None, max_length=255)
    description: str
    requirements: str | None = None
    location: str | None = Field(default=None, max_length=255)
    modality: str | None = Field(default=None, max_length=50)
    source: str = "manual"
    external_id: str | None = None
    url: HttpUrl | None = None


class JobCreate(JobBase):
    pass


class JobRead(JobBase):
    id: int
    status: str

    model_config = {"from_attributes": True}


class JobRecommendationRead(BaseModel):
    job: JobRead
    final_score: float
    rules_score: float
    semantic_score: float
    matching_skills: list[str]
    missing_skills: list[str]
    score_breakdown: dict | None = None
