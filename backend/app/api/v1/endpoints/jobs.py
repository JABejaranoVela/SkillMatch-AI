from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.job import Job
from app.models.resume import Resume
from app.models.user import User
from app.schemas.job import JobCreate, JobRead, JobRecommendationRead
from app.services.jobs_import.importer import import_jobs_from_text
from app.services.jobs_import.profile_search import build_job_search_terms
from app.services.jobs_import.remotive import sync_remotive_jobs
from app.services.jobs_import.tecnoempleo import sync_tecnoempleo_jobs
from app.services.embeddings.semantic import ensure_job_embedding, ensure_profile_embedding
from app.services.matching.rules import calculate_hybrid_match

router = APIRouter()


@router.get("", response_model=list[JobRead])
def list_jobs(db: Annotated[Session, Depends(get_db)]) -> list[Job]:
    return list(db.scalars(select(Job).order_by(Job.created_at.desc())))


@router.post("", response_model=JobRead, status_code=status.HTTP_201_CREATED)
def create_job(
    payload: JobCreate,
    db: Annotated[Session, Depends(get_db)],
    _current_user: Annotated[User, Depends(get_current_user)],
) -> Job:
    job = Job(**payload.model_dump(mode="json"))
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


@router.post("/import")
def import_jobs(
    file: UploadFile,
    db: Annotated[Session, Depends(get_db)],
    _current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    raw_content = file.file.read()
    content = raw_content.decode("utf-8-sig")
    try:
        return import_jobs_from_text(db, content, file.filename or "jobs.json")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/sync/external-api")
def sync_external_api(
    db: Annotated[Session, Depends(get_db)],
    _current_user: Annotated[User, Depends(get_current_user)],
    search: str | None = None,
    limit: int | None = None,
) -> dict:
    try:
        return sync_remotive_jobs(db=db, search=search, limit=limit)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/sync/profile")
def sync_jobs_for_active_profile(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    limit: int | None = None,
) -> dict:
    profile = _get_active_profile(db, current_user.id)
    search_terms = build_job_search_terms(profile)

    tecnoempleo_result = sync_tecnoempleo_jobs(
        db=db,
        search_terms=search_terms,
        limit=limit,
    )
    return {
        "profile_type": profile.profile_type,
        "search_terms": search_terms,
        "sources": [tecnoempleo_result],
    }


@router.get("/recommended", response_model=list[JobRecommendationRead])
def recommended_jobs(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> list[dict]:
    resume = _get_active_resume(db, current_user.id)
    profile = resume.profile
    ensure_profile_embedding(profile, resume.clean_text)
    jobs = list(
        db.scalars(
            select(Job)
            .where(Job.source == "tecnoempleo")
            .order_by(Job.created_at.desc())
        )
    )
    recommendations: list[dict] = []
    for job in jobs:
        ensure_job_embedding(job)
        score = calculate_hybrid_match(profile, job)
        recommendations.append(
            {
                "job": job,
                "final_score": score["final_score"],
                "rules_score": score["rules_score"],
                "semantic_score": score["semantic_score"],
                "matching_skills": score["explanation"]["matching_skills"],
                "missing_skills": score["explanation"]["missing_skills"],
                "score_breakdown": score["explanation"]["score_breakdown"],
            }
        )
    db.commit()
    return sorted(recommendations, key=lambda item: item["final_score"], reverse=True)


@router.get("/{job_id}", response_model=JobRead)
def get_job(job_id: int, db: Annotated[Session, Depends(get_db)]) -> Job:
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Oferta no encontrada")
    return job


def _get_active_profile(db: Session, user_id: int):
    resume = _get_active_resume(db, user_id)
    return resume.profile


def _get_active_resume(db: Session, user_id: int) -> Resume:
    resume = db.scalar(
        select(Resume)
        .where(Resume.user_id == user_id, Resume.is_active.is_(True))
        .order_by(Resume.created_at.desc())
    )
    if not resume:
        raise HTTPException(status_code=404, detail="No hay CV activo")
    if not resume.profile:
        raise HTTPException(status_code=409, detail="Procesa el CV antes de buscar ofertas")
    return resume
