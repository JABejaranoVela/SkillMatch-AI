from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.api.v1.endpoints.feedback import create_feedback
from app.api.v1.endpoints.jobs import RECOMMENDED_SOURCES, _paginate_items
from app.api.v1.router import api_router
from app.models.job import Job
from app.schemas.feedback import FeedbackCreate
from app.services.jobs_import.upsert import upsert_job


class DummySession:
    def __init__(self, job: Job | None = None) -> None:
        self.job = job
        self.added: list[Job] = []

    def add(self, job: Job) -> None:
        self.added.append(job)

    def get(self, model, item_id: int):
        return self.job


def job_detail(external_id: str = "job-1", title: str = "Backend Python") -> dict:
    return {
        "external_id": external_id,
        "title": title,
        "company": "SkillMatch",
        "description": "API con Python, FastAPI y PostgreSQL",
        "requirements": "Python, FastAPI, SQL",
        "location": "España",
        "modality": "remoto",
        "url": "https://example.com/job-1",
    }


def test_upsert_imports_once_and_reuses_process_cache() -> None:
    db = DummySession()
    existing_jobs: dict[str, Job] = {}

    result = upsert_job(db, "tecnoempleo", job_detail(), existing_jobs)

    assert result == "imported"
    assert len(db.added) == 1
    assert existing_jobs["job-1"] is db.added[0]


def test_upsert_keeps_embedding_when_offer_text_is_unchanged() -> None:
    existing = Job(source="tecnoempleo", **job_detail())
    existing.embedding = [0.1] * 384
    db = DummySession()

    result = upsert_job(db, "tecnoempleo", job_detail(), {"job-1": existing})

    assert result == "unchanged"
    assert existing.embedding == [0.1] * 384


def test_upsert_invalidates_embedding_when_offer_text_changes() -> None:
    existing = Job(source="tecnoempleo", **job_detail())
    existing.embedding = [0.1] * 384
    db = DummySession()

    result = upsert_job(
        db,
        "tecnoempleo",
        job_detail(title="Backend Python Senior"),
        {"job-1": existing},
    )

    assert result == "updated"
    assert existing.embedding is None


def test_feedback_rejects_unknown_job_with_404() -> None:
    payload = FeedbackCreate(job_id=9999, interaction_type="saved")
    current_user = SimpleNamespace(id=1)

    with pytest.raises(HTTPException) as exc_info:
        create_feedback(payload=payload, db=DummySession(job=None), current_user=current_user)

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "Oferta no encontrada"


def test_public_api_no_longer_exposes_matching_router() -> None:
    paths = [getattr(route, "path", "") for route in api_router.routes]

    assert not any(path.startswith("/matching") for path in paths)


def test_recommendations_only_use_spanish_job_sources() -> None:
    assert RECOMMENDED_SOURCES == ("tecnoempleo", "infojobs")


@pytest.mark.parametrize(
    ("offset", "expected_items", "expected_has_more"),
    [
        (0, list(range(20)), True),
        (20, list(range(20, 40)), True),
        (40, list(range(40, 50)), False),
        (50, [], False),
    ],
)
def test_recommendation_pagination(
    offset: int,
    expected_items: list[int],
    expected_has_more: bool,
) -> None:
    page, total, has_more = _paginate_items(list(range(50)), limit=20, offset=offset)

    assert page == expected_items
    assert total == 50
    assert has_more is expected_has_more
