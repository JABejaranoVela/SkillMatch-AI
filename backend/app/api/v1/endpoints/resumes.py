from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.resume import Resume
from app.models.user import User
from app.schemas.resume import ProfileRead, ResumeRead
from app.services.cv_processing.processor import process_resume
from app.services.cv_processing.storage import save_resume_file

router = APIRouter()


@router.post("/upload", response_model=ResumeRead, status_code=status.HTTP_201_CREATED)
def upload_resume(
    file: UploadFile,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> Resume:
    stored = save_resume_file(file, current_user.id)
    db.query(Resume).filter(Resume.user_id == current_user.id, Resume.is_active.is_(True)).update(
        {"is_active": False},
        synchronize_session=False,
    )
    resume = Resume(
        user_id=current_user.id,
        filename=stored.original_filename,
        file_path=stored.path,
        file_type=stored.extension,
        is_active=True,
    )
    db.add(resume)
    db.commit()
    db.refresh(resume)
    return resume


@router.get("", response_model=list[ResumeRead])
def list_resumes(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
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
    current_user: Annotated[User, Depends(get_current_user)],
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
    current_user: Annotated[User, Depends(get_current_user)],
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
    current_user: Annotated[User, Depends(get_current_user)],
) -> Resume:
    resume = db.get(Resume, resume_id)
    if not resume or resume.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="CV no encontrado")
    return resume


@router.get("/{resume_id}/profile", response_model=ProfileRead)
def get_profile(
    resume_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    resume = db.get(Resume, resume_id)
    if not resume or resume.user_id != current_user.id or not resume.profile:
        raise HTTPException(status_code=404, detail="Perfil no encontrado")
    return resume.profile


@router.post("/{resume_id}/process", response_model=ProfileRead)
def process_resume_endpoint(
    resume_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    resume = db.get(Resume, resume_id)
    if not resume or resume.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="CV no encontrado")
    return process_resume(db, resume)
