from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, Enum, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class InteractionType(StrEnum):
    VIEWED = "viewed"
    SAVED = "saved"
    DISCARDED = "discarded"
    APPLIED = "applied"


class UserJobInteraction(Base):
    __tablename__ = "user_job_interactions"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id"), index=True)
    match_result_id: Mapped[int | None] = mapped_column(
        ForeignKey("match_results.id"), nullable=True, index=True
    )
    interaction_type: Mapped[InteractionType] = mapped_column(Enum(InteractionType))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

