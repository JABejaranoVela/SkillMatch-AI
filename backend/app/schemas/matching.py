from pydantic import BaseModel

from app.schemas.job import JobRead


class MatchResultRead(BaseModel):
    id: int
    job_id: int
    rules_score: float
    semantic_score: float
    final_score: float
    explanation: dict
    algorithm_version: str
    job: JobRead | None = None

    model_config = {"from_attributes": True}
