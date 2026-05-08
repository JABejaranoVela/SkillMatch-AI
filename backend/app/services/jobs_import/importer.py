import csv
import json
from io import StringIO

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.job import Job


REQUIRED_JOB_FIELDS = {"title", "description"}


def import_jobs_from_text(db: Session, content: str, filename: str) -> dict:
    extension = filename.lower().rsplit(".", maxsplit=1)[-1]
    if extension == "json":
        records = _parse_json(content)
    elif extension == "csv":
        records = _parse_csv(content)
    else:
        raise ValueError("Formato no soportado. Usa CSV o JSON")

    imported = 0
    skipped = 0
    errors: list[str] = []

    for index, record in enumerate(records, start=1):
        missing = REQUIRED_JOB_FIELDS - set(record)
        if missing:
            skipped += 1
            errors.append(f"Registro {index}: faltan campos {', '.join(sorted(missing))}")
            continue

        existing_job = None
        if record.get("external_id"):
            existing_job = db.scalar(
                select(Job).where(
                    Job.source == record.get("source", "import"),
                    Job.external_id == record["external_id"],
                )
            )

        if existing_job:
            skipped += 1
            continue

        db.add(
            Job(
                title=record["title"],
                company=record.get("company"),
                description=record["description"],
                requirements=record.get("requirements"),
                location=record.get("location"),
                modality=record.get("modality"),
                source=record.get("source", "import"),
                external_id=record.get("external_id"),
                url=record.get("url"),
            )
        )
        imported += 1

    db.commit()
    return {"imported": imported, "skipped": skipped, "errors": errors}


def _parse_json(content: str) -> list[dict]:
    payload = json.loads(content)
    if isinstance(payload, dict):
        payload = payload.get("jobs", [])
    if not isinstance(payload, list):
        raise ValueError("El JSON debe ser una lista de ofertas o un objeto con clave jobs")
    return payload


def _parse_csv(content: str) -> list[dict]:
    reader = csv.DictReader(StringIO(content))
    return [dict(row) for row in reader]

