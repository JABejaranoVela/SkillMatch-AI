from pydantic import BaseModel


class FeedbackCreate(BaseModel):
    job_id: int
    match_result_id: int | None = None
    interaction_type: str


class FeedbackRead(FeedbackCreate):
    id: int

    model_config = {"from_attributes": True}

