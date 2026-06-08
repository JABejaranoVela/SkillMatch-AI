from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.job import Job

EMBEDDING_FIELDS = ("title", "company", "description", "requirements", "location", "modality")
UPSERT_FIELDS = (*EMBEDDING_FIELDS, "url")


def load_existing_jobs(db: Session, source: str) -> dict[str, Job]:
    jobs = db.scalars(select(Job).where(Job.source == source)).all()
    return {job.external_id: job for job in jobs if job.external_id}


def upsert_job(
    db: Session,
    source: str,
    detail: dict,
    existing_jobs: dict[str, Job],
) -> str:
    external_id = detail["external_id"]
    existing_job = existing_jobs.get(external_id)
    if existing_job is None:
        job = Job(source=source, **detail)
        db.add(job)
        existing_jobs[external_id] = job
        return "imported"

    embedding_changed = False
    changed = False
    for field in UPSERT_FIELDS:
        new_value = detail.get(field)
        if getattr(existing_job, field) != new_value:
            setattr(existing_job, field, new_value)
            changed = True
            if field in EMBEDDING_FIELDS:
                embedding_changed = True

    if embedding_changed:
        existing_job.embedding = None
    return "updated" if changed else "unchanged"
