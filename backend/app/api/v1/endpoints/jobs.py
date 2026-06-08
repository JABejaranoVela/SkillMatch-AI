from datetime import datetime
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import settings
from app.db.session import SessionLocal, get_db
from app.models.job import Job, JobSearchTask, JobStatus
from app.models.resume import Resume
from app.models.user import User
from app.schemas.job import JobCreate, JobRead, JobRecommendationRead, JobSearchTaskRead
from app.services.embeddings.semantic import ensure_job_embedding, ensure_profile_embedding
from app.services.jobs_import.importer import import_jobs_from_text
from app.services.jobs_import.infojobs import sync_infojobs_jobs
from app.services.jobs_import.profile_search import build_job_search_terms
from app.services.jobs_import.tecnoempleo import sync_tecnoempleo_jobs
from app.services.matching.rules import calculate_hybrid_match

router = APIRouter()

RECOMMENDED_SOURCES = ("tecnoempleo", "infojobs")


@router.get("", response_model=list[JobRead])
def list_jobs(db: Annotated[Session, Depends(get_db)]) -> list[Job]:
    return list(
        db.scalars(
            select(Job)
            .where(Job.source.in_(RECOMMENDED_SOURCES))
            .order_by(Job.created_at.desc())
        )
    )


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


@router.post("/search/profile", response_model=JobSearchTaskRead, status_code=status.HTTP_202_ACCEPTED)
def start_profile_job_search(
    background_tasks: BackgroundTasks,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    limit: int | None = None,
) -> JobSearchTask:
    _get_active_profile(db, current_user.id)
    task = JobSearchTask(
        task_id=uuid4().hex,
        user_id=current_user.id,
        status="pending",
        message="Búsqueda de ofertas en cola",
        sources={"items": []},
        imported=0,
        updated=0,
        skipped=0,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    background_tasks.add_task(_run_profile_job_search, task.task_id, current_user.id, limit)
    return task


@router.get("/search/{task_id}", response_model=JobSearchTaskRead)
def get_job_search_status(
    task_id: str,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> JobSearchTask:
    task = db.scalar(
        select(JobSearchTask).where(
            JobSearchTask.task_id == task_id,
            JobSearchTask.user_id == current_user.id,
        )
    )
    if not task:
        raise HTTPException(status_code=404, detail="Búsqueda no encontrada")
    return task


@router.get("/recommended", response_model=list[JobRecommendationRead])
def recommended_jobs(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> list[dict]:
    resume = _get_active_resume(db, current_user.id)
    profile = resume.profile
    ensure_profile_embedding(profile, resume.clean_text)
    jobs = _latest_recommendable_jobs(db)

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
    if not job or job.source not in RECOMMENDED_SOURCES:
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


def _latest_recommendable_jobs(db: Session) -> list[Job]:
    return list(
        db.scalars(
            select(Job)
            .where(Job.status == JobStatus.ACTIVE, Job.source.in_(RECOMMENDED_SOURCES))
            .order_by(Job.created_at.desc())
            .limit(settings.RECOMMENDATIONS_LIMIT)
        )
    )


def _run_profile_job_search(task_id: str, user_id: int, limit: int | None = None) -> None:
    db = SessionLocal()
    try:
        _update_search_task(
            db,
            task_id,
            status="searching",
            message="Buscando ofertas en portales españoles...",
        )
        profile = _get_active_profile(db, user_id)
        resume = _get_active_resume(db, user_id)
        search_terms = build_job_search_terms(profile)

        _update_search_task(
            db,
            task_id,
            status="importing",
            message="Importando ofertas desde Tecnoempleo e InfoJobs...",
        )
        source_results = [
            sync_tecnoempleo_jobs(db=db, search_terms=search_terms, limit=limit),
            sync_infojobs_jobs(db=db, search_terms=search_terms, limit=limit),
        ]

        _update_search_task(
            db,
            task_id,
            status="ranking",
            message="Calculando compatibilidad con tu CV...",
        )
        ensure_profile_embedding(profile, resume.clean_text)
        for job in _latest_recommendable_jobs(db):
            ensure_job_embedding(job)
        db.commit()

        imported = sum(int(result.get("imported", 0)) for result in source_results)
        updated = sum(int(result.get("updated", 0)) for result in source_results)
        skipped = sum(int(result.get("skipped", 0)) for result in source_results)
        _update_search_task(
            db,
            task_id,
            status="completed",
            message="Búsqueda terminada",
            sources={"items": source_results, "search_terms": search_terms},
            imported=imported,
            updated=updated,
            skipped=skipped,
        )
    except Exception as exc:
        db.rollback()
        _update_search_task(
            db,
            task_id,
            status="failed",
            message="No se pudo completar la búsqueda",
            error=str(exc),
        )
    finally:
        db.close()


def _update_search_task(db: Session, task_id: str, **values) -> None:
    task = db.scalar(select(JobSearchTask).where(JobSearchTask.task_id == task_id))
    if not task:
        return
    for key, value in values.items():
        setattr(task, key, value)
    task.updated_at = datetime.utcnow()
    db.commit()
