from datetime import datetime

from sqlalchemy.orm import Session

from app.models.profile import ProfessionalProfile
from app.models.resume import Resume, ResumeStatus
from app.services.cv_processing.extractor import extract_text_from_file
from app.services.cv_processing.profile_builder import build_profile_from_text
from app.services.embeddings.semantic import ensure_profile_embedding
from app.services.nlp.normalization import normalize_text


def process_resume(db: Session, resume: Resume) -> ProfessionalProfile:
    resume.status = ResumeStatus.PROCESSING
    db.commit()

    try:
        raw_text = extract_text_from_file(resume.file_path)
        clean_text = normalize_text(raw_text)
        profile_data = build_profile_from_text(clean_text)

        resume.raw_text = raw_text
        resume.clean_text = clean_text
        resume.status = ResumeStatus.PROCESSED
        resume.processed_at = datetime.utcnow()

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
    except Exception:
        resume.status = ResumeStatus.FAILED
        db.commit()
        raise
