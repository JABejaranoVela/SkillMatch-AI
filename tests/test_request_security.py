from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.request_security import AuthenticatedOriginMiddleware
from app import main as main_module
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


def make_app_settings(environment: str) -> Settings:
    return Settings(
        _env_file=None,
        ENVIRONMENT=environment,
        DATABASE_URL=(
            "postgresql+psycopg://skillmatch_app:strong-password@db:5432/skillmatch"
        ),
        SECRET_KEY="a-secure-production-secret-with-more-than-32-characters",
        COOKIE_SECURE=environment == "production",
        COOKIE_SAMESITE="lax",
        FRONTEND_URL=(
            "https://app.skillmatch.invalid"
            if environment == "production"
            else "http://localhost:4200"
        ),
        BACKEND_CORS_ORIGINS=[
            (
                "https://app.skillmatch.invalid"
                if environment == "production"
                else "http://localhost:4200"
            )
        ],
        EMAIL_PROVIDER="brevo" if environment == "production" else "console",
        BREVO_API_KEY=(
            "xkeysib-not-real-but-valid-looking-for-tests"
            if environment == "production"
            else None
        ),
        EMAIL_FROM=(
            "SkillMatch AI <noreply@skillmatchai.com>"
            if environment == "production"
            else "SkillMatch AI <noreply@example.com>"
        ),
        EMAIL_PAYLOAD_ENCRYPTION_KEY=(
            "VVHWBaZ4O-F3O_MKPOPbtRm0T44ay8fjkfFKyhVX04c="
        ),
    )


def test_openapi_and_docs_are_disabled_in_production(monkeypatch) -> None:
    monkeypatch.setattr(main_module, "settings", make_app_settings("production"))
    monkeypatch.setattr(main_module, "warm_up_embeddings_model", lambda: None)
    client = TestClient(main_module.create_app())

    assert client.get("/docs").status_code == 404
    assert client.get("/redoc").status_code == 404
    assert client.get("/api/v1/openapi.json").status_code == 404


def test_openapi_remains_available_outside_production(monkeypatch) -> None:
    monkeypatch.setattr(main_module, "settings", make_app_settings("development"))
    monkeypatch.setattr(main_module, "warm_up_embeddings_model", lambda: None)
    client = TestClient(main_module.create_app())

    assert client.get("/api/v1/openapi.json").status_code == 200
