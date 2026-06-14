from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.request_security import AuthenticatedOriginMiddleware
from app.main import create_app


def make_client() -> TestClient:
    app = FastAPI()
    app.add_middleware(
        AuthenticatedOriginMiddleware,
        app_settings=Settings(_env_file=None),
    )

    @app.post("/write")
    def write():
        return {"ok": True}

    return TestClient(app)


def test_authenticated_write_accepts_configured_origin() -> None:
    client = make_client()

    response = client.post(
        "/write",
        cookies={"skillmatch_session": "session-token"},
        headers={"Origin": "http://localhost:4200"},
    )

    assert response.status_code == 200


def test_authenticated_write_rejects_missing_or_foreign_origin() -> None:
    client = make_client()

    missing = client.post(
        "/write",
        cookies={"skillmatch_session": "session-token"},
    )
    foreign = client.post(
        "/write",
        cookies={"skillmatch_session": "session-token"},
        headers={"Origin": "https://attacker.example"},
    )

    assert missing.status_code == 403
    assert foreign.status_code == 403


def test_public_write_without_session_cookie_does_not_require_origin() -> None:
    response = make_client().post("/write")

    assert response.status_code == 200


def test_cors_allows_credentials_only_for_configured_origin() -> None:
    client = TestClient(create_app())

    allowed = client.options(
        "/api/v1/health",
        headers={
            "Origin": "http://localhost:4200",
            "Access-Control-Request-Method": "GET",
        },
    )
    denied = client.options(
        "/api/v1/health",
        headers={
            "Origin": "https://attacker.example",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert allowed.headers["access-control-allow-origin"] == "http://localhost:4200"
    assert allowed.headers["access-control-allow-credentials"] == "true"
    assert "access-control-allow-origin" not in denied.headers
