from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.feedback import InteractionType, UserJobInteraction
from app.models.user import User
from app.schemas.feedback import FeedbackCreate, FeedbackRead

router = APIRouter()


@router.post("", response_model=FeedbackRead, status_code=status.HTTP_201_CREATED)
def create_feedback(
    payload: FeedbackCreate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> UserJobInteraction:
    try:
        interaction_type = InteractionType(payload.interaction_type)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Tipo de feedback no valido") from exc

    interaction = UserJobInteraction(
        user_id=current_user.id,
        job_id=payload.job_id,
        match_result_id=payload.match_result_id,
        interaction_type=interaction_type,
    )
    db.add(interaction)
    db.commit()
    db.refresh(interaction)
    return interaction


@router.get("/me", response_model=list[FeedbackRead])
def list_my_feedback(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> list[UserJobInteraction]:
    stmt = select(UserJobInteraction).where(UserJobInteraction.user_id == current_user.id)
    return list(db.scalars(stmt))
