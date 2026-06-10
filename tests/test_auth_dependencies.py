from types import SimpleNamespace

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.api.deps import get_active_user, get_current_user
from app.api.v1.endpoints.jobs import router as jobs_router
from app.db.session import get_db
from app.models.user import UserStatus


def test_active_user_can_access_verified_features() -> None:
    user = SimpleNamespace(status=UserStatus.ACTIVE, email_verified_at=object())

    assert get_active_user(user) is user


def test_pending_user_cannot_access_verified_features() -> None:
    user = SimpleNamespace(status=UserStatus.PENDING, email_verified_at=None)

    with pytest.raises(HTTPException) as exc_info:
        get_active_user(user)

    assert exc_info.value.status_code == 403
    assert "verificar" in exc_info.value.detail.lower()


def test_active_but_unverified_user_cannot_access_verified_features() -> None:
    user = SimpleNamespace(status=UserStatus.ACTIVE, email_verified_at=None)

    with pytest.raises(HTTPException) as exc_info:
        get_active_user(user)

    assert exc_info.value.status_code == 403


class EmptyJobSession:
    def get(self, _model, _item_id):
        return None


def protected_jobs_client(user) -> TestClient:
    app = FastAPI()
    app.include_router(jobs_router, prefix="/jobs")
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: EmptyJobSession()
    return TestClient(app)


def test_pending_user_cannot_access_protected_job_endpoint() -> None:
    user = SimpleNamespace(status=UserStatus.PENDING, email_verified_at=None)

    response = protected_jobs_client(user).get("/jobs/1")

    assert response.status_code == 403
    assert "verificar" in response.json()["detail"].lower()


def test_active_user_can_reach_protected_job_endpoint() -> None:
    user = SimpleNamespace(
        status=UserStatus.ACTIVE,
        email_verified_at=object(),
    )

    response = protected_jobs_client(user).get("/jobs/1")

    assert response.status_code == 404
    assert response.json()["detail"] == "Oferta no encontrada"
