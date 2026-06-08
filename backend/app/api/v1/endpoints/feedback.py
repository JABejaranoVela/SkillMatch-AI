from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.feedback import InteractionType, UserJobInteraction
from app.models.job import Job
from app.models.user import User
from app.schemas.feedback import FeedbackCreate, FeedbackJobRead, FeedbackRead

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
        raise HTTPException(status_code=400, detail="Tipo de feedback no válido") from exc

    if not db.get(Job, payload.job_id):
        raise HTTPException(status_code=404, detail="Oferta no encontrada")

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


@router.get("/me/jobs", response_model=list[FeedbackJobRead])
def list_my_feedback_jobs(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    interaction_type: str | None = None,
) -> list[dict]:
    if interaction_type:
        try:
            visible_types = {InteractionType(interaction_type)}
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Tipo de feedback no válido") from exc
    else:
        visible_types = {InteractionType.SAVED, InteractionType.APPLIED}

    interactions = db.scalars(
        select(UserJobInteraction)
        .where(UserJobInteraction.user_id == current_user.id)
        .order_by(UserJobInteraction.created_at.desc(), UserJobInteraction.id.desc())
    ).all()

    latest_by_job: dict[int, UserJobInteraction] = {}
    for interaction in interactions:
        latest_by_job.setdefault(interaction.job_id, interaction)

    results: list[dict] = []
    for interaction in latest_by_job.values():
        if interaction.interaction_type not in visible_types:
            continue
        job = db.get(Job, interaction.job_id)
        if not job:
            continue
        results.append(
            {
                "id": interaction.id,
                "job_id": interaction.job_id,
                "match_result_id": interaction.match_result_id,
                "interaction_type": interaction.interaction_type,
                "created_at": interaction.created_at,
                "job": job,
            }
        )
    return results
