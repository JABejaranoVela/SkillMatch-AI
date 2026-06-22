from types import SimpleNamespace

import pytest
from fastapi import BackgroundTasks, HTTPException

from app.api.v1.endpoints import jobs as jobs_endpoint
from app.models.job import JobSearchTask


class StartSearchSession:
    def __init__(self) -> None:
        self.added = None
        self.commits = 0
        self.refreshed = None

    def add(self, item) -> None:
        self.added = item

    def commit(self) -> None:
        self.commits += 1

    def refresh(self, item) -> None:
        self.refreshed = item


class WorkerSearchSession:
    def __init__(self, task: JobSearchTask) -> None:
        self.task = task
        self.status_history: list[str] = []
        self.commits = 0
        self.rollbacks = 0
        self.closed = False

    def scalar(self, _statement):
        return self.task

    def commit(self) -> None:
        self.commits += 1
        self.status_history.append(self.task.status)

    def rollback(self) -> None:
        self.rollbacks += 1

    def close(self) -> None:
        self.closed = True


def test_start_profile_search_rejects_active_task_before_rate_limit(monkeypatch) -> None:
    monkeypatch.setattr(jobs_endpoint, "_get_active_profile", lambda _db, _user_id: object())
    monkeypatch.setattr(
        jobs_endpoint,
        "_get_active_search_task",
        lambda _db, _user_id: JobSearchTask(status="searching"),
    )

    def fail_rate_limit(**_kwargs):
        raise AssertionError("rate limit should not be consumed for active searches")

    monkeypatch.setattr(jobs_endpoint, "consume_rate_limit", fail_rate_limit)

    with pytest.raises(HTTPException) as exc_info:
        jobs_endpoint.start_profile_job_search(
            BackgroundTasks(),
            StartSearchSession(),
            SimpleNamespace(id=1),
        )

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail == jobs_endpoint.ACTIVE_JOB_SEARCH_MESSAGE


def test_start_profile_search_rate_limit_returns_retry_after(monkeypatch) -> None:
    monkeypatch.setattr(jobs_endpoint, "_get_active_profile", lambda _db, _user_id: object())
    monkeypatch.setattr(jobs_endpoint, "_get_active_search_task", lambda _db, _user_id: None)
    monkeypatch.setattr(
        jobs_endpoint,
        "consume_rate_limit",
        lambda **_kwargs: SimpleNamespace(allowed=False, retry_after=123, count=7),
    )

    with pytest.raises(HTTPException) as exc_info:
        jobs_endpoint.start_profile_job_search(
            BackgroundTasks(),
            StartSearchSession(),
            SimpleNamespace(id=1),
        )

    assert exc_info.value.status_code == 429
    assert exc_info.value.headers == {"Retry-After": "123"}
    assert exc_info.value.detail == jobs_endpoint.JOB_SEARCH_RATE_LIMIT_MESSAGE


def test_start_profile_search_creates_pending_task_after_rate_limit(monkeypatch) -> None:
    db = StartSearchSession()
    background_tasks = BackgroundTasks()
    monkeypatch.setattr(jobs_endpoint, "_get_active_profile", lambda _db, _user_id: object())
    monkeypatch.setattr(jobs_endpoint, "_get_active_search_task", lambda _db, _user_id: None)
    monkeypatch.setattr(
        jobs_endpoint,
        "consume_rate_limit",
        lambda **_kwargs: SimpleNamespace(allowed=True, retry_after=3600, count=1),
    )

    task = jobs_endpoint.start_profile_job_search(
        background_tasks,
        db,
        SimpleNamespace(id=42),
    )

    assert task is db.added
    assert task.status == "pending"
    assert task.user_id == 42
    assert db.commits == 1
    assert db.refreshed is task
    assert len(background_tasks.tasks) == 1


def test_run_profile_job_search_keeps_public_state_sequence(monkeypatch) -> None:
    task = JobSearchTask(task_id="task-1", user_id=10, status="pending")
    db = WorkerSearchSession(task)
    monkeypatch.setattr(jobs_endpoint, "SessionLocal", lambda: db)
    monkeypatch.setattr(jobs_endpoint, "_get_active_profile", lambda _db, _user_id: object())
    monkeypatch.setattr(jobs_endpoint, "_get_active_resume", lambda _db, _user_id: object())
    monkeypatch.setattr(jobs_endpoint, "build_job_search_terms", lambda _profile: ["python"])
    monkeypatch.setattr(
        jobs_endpoint,
        "sync_tecnoempleo_jobs",
        lambda **_kwargs: {"imported": 1, "updated": 2, "skipped": 3},
    )
    monkeypatch.setattr(
        jobs_endpoint,
        "sync_infojobs_jobs",
        lambda **_kwargs: {"imported": 4, "updated": 5, "skipped": 6},
    )
    monkeypatch.setattr(
        jobs_endpoint,
        "_refresh_recommendation_results",
        lambda _db, _user_id, _resume: None,
    )

    jobs_endpoint._run_profile_job_search("task-1", user_id=10)

    assert db.status_history == ["searching", "importing", "ranking", "completed"]
    assert task.status == "completed"
    assert task.sources == {
        "items": [
            {"imported": 1, "updated": 2, "skipped": 3},
            {"imported": 4, "updated": 5, "skipped": 6},
        ]
    }
    assert "search_terms" not in task.sources
    assert task.imported == 5
    assert task.updated == 7
    assert task.skipped == 9
    assert db.closed is True


def test_run_profile_job_search_stores_safe_error(monkeypatch) -> None:
    task = JobSearchTask(task_id="task-1", user_id=10, status="pending")
    db = WorkerSearchSession(task)
    monkeypatch.setattr(jobs_endpoint, "SessionLocal", lambda: db)
    monkeypatch.setattr(jobs_endpoint, "_get_active_profile", lambda _db, _user_id: object())
    monkeypatch.setattr(jobs_endpoint, "_get_active_resume", lambda _db, _user_id: object())
    monkeypatch.setattr(jobs_endpoint, "build_job_search_terms", lambda _profile: ["python"])

    def fail_sync(**_kwargs):
        raise RuntimeError("private cv text and external stack details")

    monkeypatch.setattr(jobs_endpoint, "sync_tecnoempleo_jobs", fail_sync)

    jobs_endpoint._run_profile_job_search("task-1", user_id=10)

    assert task.status == "failed"
    assert task.message == jobs_endpoint.SAFE_JOB_SEARCH_ERROR
    assert task.error == jobs_endpoint.SAFE_JOB_SEARCH_ERROR
    assert "private cv text" not in task.error
    assert db.rollbacks == 1
    assert db.closed is True


def test_processing_is_treated_as_active_legacy_status() -> None:
    assert "processing" in jobs_endpoint.ACTIVE_JOB_SEARCH_STATUSES
