import html
import re

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.job import Job
from app.services.nlp.skills import detect_skills


def sync_arbeitnow_jobs(db: Session, search_terms: list[str], limit: int | None = None) -> dict:
    max_records = limit or settings.PROFILE_JOB_IMPORT_LIMIT
    response = httpx.get(settings.ARBEITNOW_API_URL, timeout=20.0)
    response.raise_for_status()
    payload = response.json()
    records = payload.get("data", []) if isinstance(payload, dict) else []

    imported = 0
    skipped = 0
    normalized_terms = [term.lower() for term in search_terms if term]

    for item in records:
        if imported >= max_records:
            break

        text_for_match = " ".join(
            [
                item.get("title") or "",
                item.get("company_name") or "",
                item.get("description") or "",
                " ".join(item.get("tags") or []),
            ]
        ).lower()
        if normalized_terms and not any(term in text_for_match for term in normalized_terms):
            continue

        external_id = str(item.get("slug") or item.get("url") or "")
        if not external_id:
            skipped += 1
            continue

        description = _clean_html(item.get("description") or "")
        tags = item.get("tags") or []
        requirements = _build_requirements(tags, description)
        modality = "remoto" if item.get("remote") else "presencial/hibrido"

        existing_job = db.scalar(
            select(Job).where(Job.source == "arbeitnow", Job.external_id == external_id)
        )
        if existing_job:
            existing_job.description = description or existing_job.description
            existing_job.requirements = requirements or existing_job.requirements
            existing_job.modality = modality
            skipped += 1
            continue

        db.add(
            Job(
                title=item.get("title") or "Oferta sin titulo",
                company=item.get("company_name"),
                description=description,
                requirements=_build_requirements(tags, description),
                location=item.get("location"),
                modality=modality,
                source="arbeitnow",
                external_id=external_id,
                url=item.get("url"),
            )
        )
        imported += 1

    db.commit()
    return {
        "source": "arbeitnow",
        "search_terms": search_terms,
        "imported": imported,
        "skipped": skipped,
        "attribution": "Jobs imported from Arbeitnow public job board API.",
    }


def _clean_html(value: str) -> str:
    without_tags = re.sub(r"<[^>]+>", " ", value)
    without_entities = html.unescape(without_tags)
    return re.sub(r"\s+", " ", without_entities).strip()


def _build_requirements(tags: list[str], description: str) -> str:
    if tags:
        return ", ".join(tags)
    detected = [skill["name"] for skill in detect_skills(description)]
    return ", ".join(detected)
