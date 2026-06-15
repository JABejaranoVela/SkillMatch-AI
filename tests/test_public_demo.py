from types import SimpleNamespace

import fitz
from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from app.api.v1.endpoints import public as public_endpoint
from app.core.config import settings
from app.schemas.public import PublicDemoAnalysisRead


def make_pdf(text: str, *, pages: int = 1) -> bytes:
    document = fitz.open()
    for _ in range(pages):
        page = document.new_page()
        if text:
            page.insert_textbox(fitz.Rect(72, 72, 540, 760), text, fontsize=11)
    data = document.tobytes()
    document.close()
    return data


@pytest.fixture
def client(monkeypatch) -> TestClient:
    monkeypatch.setattr(
        public_endpoint,
        "consume_rate_limit",
        lambda **_kwargs: SimpleNamespace(allowed=True, retry_after=0),
    )
    app = FastAPI()
    app.include_router(public_endpoint.router, prefix="/api/v1/public")
    return TestClient(app)


def test_valid_pdf_returns_public_demo_profile_without_authentication(client: TestClient) -> None:
    pdf = make_pdf(
        "Full Stack Developer con experiencia en Python, FastAPI, Angular, "
        "TypeScript, PostgreSQL, SQL y Docker. Ingles B2. "
        "Grado Superior en Desarrollo de Aplicaciones Multiplataforma."
    )

    response = client.post(
        "/api/v1/public/demo/analyze-cv",
        files={"file": ("cv.pdf", pdf, "application/pdf")},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["is_demo"] is True
    assert payload["profile_type"] == "Full Stack Developer"
    assert {"Python", "FastAPI", "Angular", "Docker"} <= set(payload["skills"])
    assert len(payload["skills"]) <= settings.PUBLIC_DEMO_SKILLS_LIMIT


def test_public_demo_route_has_no_database_or_auth_dependencies() -> None:
    route = next(
        route
        for route in public_endpoint.router.routes
        if route.path == "/demo/analyze-cv"
    )

    assert route.dependant.dependencies == []


@pytest.mark.parametrize(
    ("filename", "content"),
    [
        ("cv.txt", b"not a pdf"),
        ("cv.pdf", b"not a pdf"),
        ("cv.pdf", b""),
    ],
)
def test_public_demo_rejects_non_pdf_files(
    client: TestClient,
    filename: str,
    content: bytes,
) -> None:
    response = client.post(
        "/api/v1/public/demo/analyze-cv",
        files={"file": (filename, content, "application/octet-stream")},
    )

    assert response.status_code == 400


def test_public_demo_rejects_pdf_without_extractable_text(client: TestClient) -> None:
    response = client.post(
        "/api/v1/public/demo/analyze-cv",
        files={"file": ("empty.pdf", make_pdf(""), "application/pdf")},
    )

    assert response.status_code == 400
    assert "texto" in response.json()["detail"].lower()


def test_public_demo_rejects_pdf_above_size_limit(
    client: TestClient,
    monkeypatch,
) -> None:
    monkeypatch.setattr(settings, "MAX_UPLOAD_SIZE_MB", 1)
    oversized = b"%PDF-" + (b"x" * (1024 * 1024))

    response = client.post(
        "/api/v1/public/demo/analyze-cv",
        files={"file": ("large.pdf", oversized, "application/pdf")},
    )

    assert response.status_code == 413


def test_public_demo_rejects_pdf_above_page_limit(
    client: TestClient,
    monkeypatch,
) -> None:
    monkeypatch.setattr(settings, "PUBLIC_DEMO_MAX_PAGES", 1)

    response = client.post(
        "/api/v1/public/demo/analyze-cv",
        files={
            "file": (
                "long.pdf",
                make_pdf("Contenido profesional suficientemente largo para analizar.", pages=2),
                "application/pdf",
            )
        },
    )

    assert response.status_code == 400
    assert "páginas" in response.json()["detail"].lower()


def test_public_demo_returns_empty_optional_collections(client: TestClient) -> None:
    pdf = make_pdf(
        "Profesional responsable con capacidad de organización, comunicación "
        "y colaboración en equipos multidisciplinares durante distintos proyectos."
    )

    response = client.post(
        "/api/v1/public/demo/analyze-cv",
        files={"file": ("generic.pdf", pdf, "application/pdf")},
    )

    assert response.status_code == 200
    payload = response.json()
    assert isinstance(payload["skills"], list)
    assert isinstance(payload["languages"], list)
    assert isinstance(payload["education"], list)


def test_public_demo_rate_limit_returns_retry_after(monkeypatch) -> None:
    monkeypatch.setattr(
        public_endpoint,
        "consume_rate_limit",
        lambda **_kwargs: SimpleNamespace(allowed=False, retry_after=900),
    )
    app = FastAPI()
    app.include_router(public_endpoint.router, prefix="/api/v1/public")
    client = TestClient(app)

    response = client.post(
        "/api/v1/public/demo/analyze-cv",
        files={"file": ("cv.pdf", make_pdf("Contenido suficiente " * 10), "application/pdf")},
    )

    assert response.status_code == 429
    assert response.headers["Retry-After"] == "900"


def test_public_demo_hides_internal_analysis_errors(client: TestClient, monkeypatch) -> None:
    def fail_analysis(_data: bytes) -> PublicDemoAnalysisRead:
        raise RuntimeError("private extracted data")

    monkeypatch.setattr(public_endpoint, "analyze_demo_pdf", fail_analysis)

    response = client.post(
        "/api/v1/public/demo/analyze-cv",
        files={"file": ("cv.pdf", make_pdf("Contenido suficiente " * 10), "application/pdf")},
    )

    assert response.status_code == 500
    assert response.json()["detail"] == "No se ha podido analizar el CV en este momento"
    assert "private extracted data" not in response.text
