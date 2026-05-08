import html
import re

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.job import Job
from app.services.nlp.skills import detect_skills


def sync_remotive_jobs(db: Session, search: str | None = None, limit: int | None = None) -> dict:
    params = {"search": search or settings.REMOTIVE_DEFAULT_SEARCH}
    max_records = limit or settings.REMOTIVE_IMPORT_LIMIT

    response = httpx.get(settings.REMOTIVE_API_URL, params=params, timeout=20.0)
    response.raise_for_status()
    payload = response.json()
    jobs = payload.get("jobs", [])[:max_records]

    imported = 0
    skipped = 0

    for item in jobs:
        external_id = str(item.get("id"))
        if not external_id:
            skipped += 1
            continue

        description = _clean_html(item.get("description") or "")
        requirements = _build_requirements(item.get("tags") or [], description)
        existing_job = db.scalar(
            select(Job).where(Job.source == "remotive", Job.external_id == external_id)
        )
        if existing_job:
            existing_job.description = description or existing_job.description
            existing_job.requirements = requirements or existing_job.requirements
            existing_job.modality = "remoto"
            skipped += 1
            continue

        db.add(
            Job(
                title=item.get("title") or "Oferta sin titulo",
                company=item.get("company_name"),
                description=description,
                requirements=requirements,
                location=item.get("candidate_required_location"),
                modality="remoto",
                source="remotive",
                external_id=external_id,
                url=item.get("url"),
            )
        )
        imported += 1

    db.commit()
    return {
        "source": "remotive",
        "search": params["search"],
        "imported": imported,
        "skipped": skipped,
        "attribution": "Jobs imported from Remotive. Keep original URLs visible.",
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
