from app.core.config import settings
from app.schemas.public import PublicDemoAnalysisRead
from app.services.cv_processing.extractor import extract_text_from_pdf_bytes
from app.services.cv_processing.profile_builder import build_profile_from_text
from app.services.nlp.normalization import normalize_text


class DemoCvValidationError(ValueError):
    pass


def analyze_demo_pdf(data: bytes) -> PublicDemoAnalysisRead:
    try:
        raw_text = extract_text_from_pdf_bytes(
            data,
            max_pages=settings.PUBLIC_DEMO_MAX_PAGES,
        )
    except ValueError as exc:
        raise DemoCvValidationError(str(exc)) from exc
    except Exception as exc:
        raise DemoCvValidationError("El archivo no es un PDF válido o no se puede leer") from exc

    clean_text = normalize_text(raw_text)
    if len(clean_text) < settings.PUBLIC_DEMO_MIN_TEXT_CHARS:
        raise DemoCvValidationError(
            "No se ha podido extraer suficiente texto del PDF"
        )

    profile_data = build_profile_from_text(clean_text)
    skills = sorted(
        profile_data.get("skills", []),
        key=lambda item: (
            -float(item.get("confidence", 0)),
            str(item.get("name", "")).lower(),
        ),
    )
    skill_names = [
        str(item["name"])
        for item in skills[: settings.PUBLIC_DEMO_SKILLS_LIMIT]
        if item.get("name")
    ]
    education = profile_data.get("education") or {}
    experience_years = profile_data.get("experience_years")
    experience_summary = (
        f"{experience_years:g} años de experiencia detectados"
        if experience_years is not None
        else None
    )

    return PublicDemoAnalysisRead(
        profile_type=profile_data["profile_type"],
        summary=profile_data["summary"],
        skills=skill_names,
        languages=list(profile_data.get("languages") or []),
        education=list(education.get("raw") or []),
        experience_summary=experience_summary,
    )
