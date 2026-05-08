from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.feedback import UserJobInteraction
from app.models.matching import MatchResult
from app.models.resume import Resume
from app.models.user import User
from app.schemas.matching import MatchResultRead
from app.models.job import Job, JobStatus
from app.core.config import settings
from app.services.embeddings.semantic import ensure_job_embedding, ensure_profile_embedding
from app.services.matching.rules import calculate_hybrid_match

router = APIRouter()


@router.post("/active", response_model=list[MatchResultRead])
def run_active_matching(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> list[MatchResult]:
    resume = db.scalar(
        select(Resume)
        .where(Resume.user_id == current_user.id, Resume.is_active.is_(True))
        .order_by(Resume.created_at.desc())
    )
    if not resume:
        raise HTTPException(status_code=404, detail="No hay CV activo")
    if not resume.profile:
        raise HTTPException(status_code=409, detail="Procesa el CV antes de calcular matching")

    jobs = db.scalars(
        select(Job).where(Job.status == JobStatus.ACTIVE, Job.source == "tecnoempleo")
    ).all()
    ensure_profile_embedding(resume.profile, resume.clean_text)
    old_result_ids = list(
        db.scalars(
            select(MatchResult.id).where(
                MatchResult.resume_id == resume.id,
                MatchResult.user_id == current_user.id,
            )
        )
    )
    if old_result_ids:
        db.query(UserJobInteraction).filter(
            UserJobInteraction.match_result_id.in_(old_result_ids)
        ).update({"match_result_id": None}, synchronize_session=False)
    db.execute(
        delete(MatchResult).where(
            MatchResult.resume_id == resume.id,
            MatchResult.user_id == current_user.id,
        )
    )
    results: list[MatchResult] = []
    for job in jobs:
        ensure_job_embedding(job)
        score = calculate_hybrid_match(resume.profile, job)
        result = MatchResult(
            user_id=current_user.id,
            resume_id=resume.id,
            job_id=job.id,
            rules_score=score["rules_score"],
            semantic_score=score["semantic_score"],
            final_score=score["final_score"],
            explanation=score["explanation"],
            algorithm_version=settings.MATCHING_ALGORITHM_VERSION,
        )
        db.add(result)
        results.append(result)

    db.commit()
    for result in results:
        db.refresh(result)
    return sorted(results, key=lambda item: item.final_score, reverse=True)


@router.post("/resumes/{resume_id}", response_model=list[MatchResultRead])
def run_matching(
    resume_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> list[MatchResult]:
    resume = db.get(Resume, resume_id)
    if not resume or resume.user_id != current_user.id or not resume.is_active:
        raise HTTPException(status_code=404, detail="CV activo no encontrado")
    return run_active_matching(db=db, current_user=current_user)


@router.get("/resumes/{resume_id}/results", response_model=list[MatchResultRead])
def list_results(
    resume_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> list[MatchResult]:
    resume = db.get(Resume, resume_id)
    if not resume or resume.user_id != current_user.id or not resume.is_active:
        raise HTTPException(status_code=404, detail="CV no encontrado")
    stmt = (
        select(MatchResult)
        .where(MatchResult.resume_id == resume_id, MatchResult.user_id == current_user.id)
        .order_by(MatchResult.final_score.desc())
    )
    return list(db.scalars(stmt))
