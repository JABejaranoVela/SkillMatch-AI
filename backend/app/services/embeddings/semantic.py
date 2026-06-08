from functools import lru_cache
from math import sqrt
from typing import Iterable

from app.core.config import settings
from app.models.job import Job
from app.models.profile import ProfessionalProfile

MAX_TEXT_CHARS = 6000


@lru_cache(maxsize=1)
def _load_model():
    if not settings.EMBEDDINGS_ENABLED:
        return None

    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(settings.EMBEDDINGS_MODEL_NAME)


def encode_text(text: str | None) -> list[float] | None:
    normalized = (text or "").strip()
    if not normalized:
        return None

    model = _load_model()
    if model is None:
        return None

    vector = model.encode(normalized[:MAX_TEXT_CHARS], normalize_embeddings=True)
    return [float(value) for value in vector.tolist()]


def warm_up_embeddings_model() -> None:
    _load_model()


def cosine_similarity(left: Iterable[float] | None, right: Iterable[float] | None) -> float:
    left_values = list(left) if left is not None else []
    right_values = list(right) if right is not None else []
    if not left_values or not right_values or len(left_values) != len(right_values):
        return 0.0

    dot = sum(a * b for a, b in zip(left_values, right_values, strict=True))
    left_norm = sqrt(sum(a * a for a in left_values))
    right_norm = sqrt(sum(b * b for b in right_values))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return float(max(0.0, min(1.0, dot / (left_norm * right_norm))))


def profile_embedding_text(profile: ProfessionalProfile, resume_text: str | None = None) -> str:
    technologies = ", ".join(profile.technologies or [])
    languages = ", ".join(profile.languages or [])
    education = ""
    if profile.education:
        raw_education = profile.education.get("raw") if isinstance(profile.education, dict) else None
        if raw_education:
            education = " ".join(str(item) for item in raw_education)

    return "\n".join(
        part
        for part in [
            f"Perfil profesional: {profile.profile_type or ''}",
            f"Resumen: {profile.summary or ''}",
            f"Tecnologias y habilidades: {technologies}",
            f"Idiomas: {languages}",
            f"Formacion: {education}",
            f"Texto del CV: {resume_text or ''}",
        ]
        if part.strip()
    )


def job_embedding_text(job: Job) -> str:
    return "\n".join(
        part
        for part in [
            f"Puesto: {job.title}",
            f"Empresa: {job.company or ''}",
            f"Modalidad: {job.modality or ''}",
            f"Ubicacion: {job.location or ''}",
            f"Descripcion: {job.description}",
            f"Requisitos: {job.requirements or ''}",
        ]
        if part.strip()
    )


def ensure_profile_embedding(
    profile: ProfessionalProfile,
    resume_text: str | None = None,
) -> list[float] | None:
    if profile.embedding is None:
        profile.embedding = encode_text(profile_embedding_text(profile, resume_text))
    return profile.embedding


def ensure_job_embedding(job: Job) -> list[float] | None:
    if job.embedding is None:
        job.embedding = encode_text(job_embedding_text(job))
    return job.embedding
