from datetime import datetime

from pydantic import BaseModel

from app.schemas.job import JobRead


class FeedbackCreate(BaseModel):
    job_id: int
    match_result_id: int | None = None
    interaction_type: str


class FeedbackRead(FeedbackCreate):
    id: int

    model_config = {"from_attributes": True}


class FeedbackJobRead(FeedbackRead):
    created_at: datetime
    job: JobRead
