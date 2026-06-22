from typing import Annotated
import logging
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from app.api.deps import get_active_user
from app.db.session import get_db
from app.models.feedback import UserJobInteraction
from app.models.matching import MatchResult
from app.models.profile import ProfessionalProfile, ProfileSkill
from app.models.resume import Resume
from app.models.user import User
from app.schemas.resume import ProfileRead, ResumeRead
from app.services.cv_processing.processor import ResumeProcessingError, process_resume
from app.services.cv_processing.storage import save_resume_file

router = APIRouter()
logger = logging.getLogger(__name__)

DELETE_RESUME_ERROR = "No se ha podido eliminar el CV en este momento."


@router.post("/upload", response_model=ResumeRead, status_code=status.HTTP_201_CREATED)
def upload_resume(
    file: UploadFile,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_active_user)],
) -> Resume:
    stored = save_resume_file(file, current_user.id)
    resume = Resume(
        user_id=current_user.id,
        filename=stored.original_filename,
        file_path=stored.path,
        file_type=stored.extension,
        is_active=False,
    )
    db.add(resume)
    db.commit()
    db.refresh(resume)
    return resume


@router.get("", response_model=list[ResumeRead])
def list_resumes(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_active_user)],
) -> list[Resume]:
    return list(
        db.scalars(
            select(Resume)
            .where(Resume.user_id == current_user.id, Resume.is_active.is_(True))
            .order_by(Resume.created_at.desc())
        )
    )


@router.get("/active", response_model=ResumeRead)
def get_active_resume(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_active_user)],
) -> Resume:
    resume = db.scalar(
        select(Resume)
        .where(Resume.user_id == current_user.id, Resume.is_active.is_(True))
        .order_by(Resume.created_at.desc())
    )
    if not resume:
        raise HTTPException(status_code=404, detail="No hay CV activo")
    return resume


@router.get("/active/profile", response_model=ProfileRead)
def get_active_profile(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_active_user)],
):
    resume = db.scalar(
        select(Resume)
        .where(Resume.user_id == current_user.id, Resume.is_active.is_(True))
        .order_by(Resume.created_at.desc())
    )
    if not resume or not resume.profile:
        raise HTTPException(status_code=404, detail="Perfil activo no encontrado")
    return resume.profile


@router.get("/{resume_id}", response_model=ResumeRead)
def get_resume(
    resume_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_active_user)],
) -> Resume:
    resume = db.get(Resume, resume_id)
    if not resume or resume.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="CV no encontrado")
    return resume


@router.get("/{resume_id}/profile", response_model=ProfileRead)
def get_profile(
    resume_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_active_user)],
):
    resume = db.get(Resume, resume_id)
    if not resume or resume.user_id != current_user.id or not resume.profile:
        raise HTTPException(status_code=404, detail="Perfil no encontrado")
    return resume.profile


@router.delete("/{resume_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_resume(
    resume_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_active_user)],
) -> None:
    resume = db.get(Resume, resume_id)
    if not resume or resume.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="CV no encontrado")

    try:
        _delete_resume_file(resume)
    except OSError as exc:
        logger.warning(
            "Resume file deletion failed",
            extra={"resume_id": resume.id, "user_id": current_user.id},
        )
        raise HTTPException(
            status_code=500,
            detail=DELETE_RESUME_ERROR,
        ) from exc

    try:
        _delete_resume_data(db, resume, current_user.id)
        db.commit()
    except Exception:
        db.rollback()
        logger.exception(
            "Resume data deletion failed",
            extra={"resume_id": resume.id, "user_id": current_user.id},
        )
        raise HTTPException(
            status_code=500,
            detail=DELETE_RESUME_ERROR,
        ) from None


@router.post("/{resume_id}/process", response_model=ProfileRead)
def process_resume_endpoint(
    resume_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_active_user)],
):
    resume = db.get(Resume, resume_id)
    if not resume or resume.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="CV no encontrado")
    try:
        return process_resume(db, resume)
    except ResumeProcessingError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.public_message) from exc


def _delete_resume_file(resume: Resume) -> None:
    path = Path(resume.file_path)
    if not path.exists():
        logger.info(
            "Resume file was already absent",
            extra={"resume_id": resume.id, "user_id": resume.user_id},
        )
        return
    path.unlink()
    logger.info(
        "Resume file deleted",
        extra={"resume_id": resume.id, "user_id": resume.user_id},
    )


def _delete_resume_data(db: Session, resume: Resume, user_id: int) -> None:
    match_result_ids = select(MatchResult.id).where(
        MatchResult.resume_id == resume.id,
        MatchResult.user_id == user_id,
    )
    db.execute(
        update(UserJobInteraction)
        .where(
            UserJobInteraction.user_id == user_id,
            UserJobInteraction.match_result_id.in_(match_result_ids),
        )
        .values(match_result_id=None)
        .execution_options(synchronize_session=False)
    )
    db.execute(
        delete(MatchResult).where(
            MatchResult.resume_id == resume.id,
            MatchResult.user_id == user_id,
        )
        .execution_options(synchronize_session=False)
    )

    profile = db.scalar(
        select(ProfessionalProfile).where(ProfessionalProfile.resume_id == resume.id)
    )
    if profile:
        db.execute(
            delete(ProfileSkill)
            .where(ProfileSkill.profile_id == profile.id)
            .execution_options(synchronize_session=False)
        )
        db.delete(profile)

    db.delete(resume)
