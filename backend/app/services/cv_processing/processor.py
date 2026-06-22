from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.profile import ProfessionalProfile
from app.models.resume import Resume, ResumeStatus
from app.services.cv_processing.extractor import CvValidationError, extract_text_from_file
from app.services.cv_processing.profile_builder import build_profile_from_text
from app.services.embeddings.semantic import ensure_profile_embedding
from app.services.nlp.normalization import normalize_text


class ResumeProcessingError(RuntimeError):
    def __init__(self, public_message: str, *, status_code: int = 500) -> None:
        super().__init__(public_message)
        self.public_message = public_message
        self.status_code = status_code


def process_resume(db: Session, resume: Resume) -> ProfessionalProfile:
    resume.status = ResumeStatus.PROCESSING
    db.commit()

    try:
        raw_text = extract_text_from_file(
            resume.file_path,
            max_pages=settings.RESUME_MAX_PAGES,
            min_text_chars=settings.RESUME_MIN_TEXT_CHARS,
        )
        clean_text = normalize_text(raw_text)
        profile_data = build_profile_from_text(clean_text)

        resume.raw_text = raw_text
        resume.clean_text = clean_text
        resume.status = ResumeStatus.PROCESSED
        resume.processed_at = _resume_timestamp()
        db.query(Resume).filter(
            Resume.user_id == resume.user_id,
            Resume.id != resume.id,
            Resume.is_active.is_(True),
        ).update(
            {"is_active": False},
            synchronize_session=False,
        )
        resume.is_active = True

        profile = resume.profile or ProfessionalProfile(resume_id=resume.id)
        profile.profile_type = profile_data["profile_type"]
        profile.summary = profile_data["summary"]
        profile.experience_years = profile_data["experience_years"]
        profile.education = profile_data["education"]
        profile.languages = profile_data["languages"]
        profile.technologies = profile_data["technologies"]
        profile.analysis = profile_data["analysis"]
        profile.embedding = None
        ensure_profile_embedding(profile, clean_text)
        db.add(profile)
        db.commit()
        db.refresh(profile)
        return profile
    except CvValidationError as exc:
        resume.status = ResumeStatus.FAILED
        resume.is_active = False
        resume.processed_at = _resume_timestamp()
        db.commit()
        raise ResumeProcessingError(str(exc), status_code=400) from exc
    except Exception as exc:
        resume.status = ResumeStatus.FAILED
        resume.is_active = False
        resume.processed_at = _resume_timestamp()
        db.commit()
        raise ResumeProcessingError(
            "No se ha podido procesar el CV en este momento.",
            status_code=500,
        ) from exc


def _resume_timestamp() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)
