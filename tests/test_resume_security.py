from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import fitz
from fastapi import FastAPI, HTTPException, UploadFile
from fastapi.testclient import TestClient
import pytest
from sqlalchemy import select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import sessionmaker
from starlette.datastructures import Headers

from app.api.deps import get_active_user
from app.api.v1.endpoints import resumes
from app.core.config import settings
from app.db.session import get_db
from app.models.resume import Resume, ResumeStatus
from app.models.user import User
from app.services.cv_processing import processor, storage
from app.services.cv_processing.extractor import CvValidationError
from app.services.cv_processing.processor import ResumeProcessingError, process_resume
from app.services.cv_processing.storage import save_resume_file
from backend_test_database import verified_test_engine


def make_upload(
    data: bytes,
    *,
    filename: str = "cv.pdf",
    content_type: str = "application/pdf",
) -> UploadFile:
    return UploadFile(
        file=BytesIO(data),
        filename=filename,
        headers=Headers({"content-type": content_type}),
    )


def make_pdf(text: str, *, pages: int = 1) -> bytes:
    document = fitz.open()
    for _ in range(pages):
        page = document.new_page()
        if text:
            page.insert_textbox(fitz.Rect(72, 72, 540, 760), text, fontsize=11)
    data = document.tobytes()
    document.close()
    return data


def make_protected_pdf() -> bytes:
    document = fitz.open()
    page = document.new_page()
    page.insert_textbox(
        fitz.Rect(72, 72, 540, 760),
        "Contenido profesional suficiente para validar un curriculum protegido.",
        fontsize=11,
    )
    data = document.tobytes(
        encryption=fitz.PDF_ENCRYPT_AES_256,
        owner_pw="owner-password",
        user_pw="user-password",
    )
    document.close()
    return data


@pytest.fixture(autouse=True)
def resume_limits(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path))
    monkeypatch.setattr(settings, "MAX_UPLOAD_SIZE_MB", 10)
    monkeypatch.setattr(settings, "RESUME_MAX_PAGES", 25)
    monkeypatch.setattr(settings, "RESUME_MIN_TEXT_CHARS", 50)


def test_save_resume_accepts_valid_pdf_after_real_validation(tmp_path) -> None:
    stored = save_resume_file(
        make_upload(
            make_pdf(
                "Full Stack Developer con experiencia en Python, FastAPI, "
                "Angular, PostgreSQL y Docker durante varios proyectos."
            )
        ),
        user_id=7,
    )

    assert stored.extension == ".pdf"
    assert stored.original_filename == "cv.pdf"
    assert stored.path.startswith(str(tmp_path))
    assert Path(stored.path).read_bytes().startswith(b"%PDF-")


def test_save_resume_removes_partial_write(monkeypatch, tmp_path):
    original_open = Path.open

    class InterruptedWriter:
        def __init__(self, stream):
            self.stream = stream

        def __enter__(self):
            return self

        def write(self, data):
            self.stream.write(data[:8])
            raise OSError("interrupted write")

        def __exit__(self, *_):
            self.stream.close()

    def interrupt_pdf_write(path, mode="r", *args, **kwargs):
        stream = original_open(path, mode, *args, **kwargs)
        if path.suffix == ".pdf" and mode in ("wb", "xb"):
            return InterruptedWriter(stream)
        return stream

    monkeypatch.setattr(Path, "open", interrupt_pdf_write)
    with pytest.raises(OSError, match="interrupted write"):
        save_resume_file(make_upload(make_pdf("Synthetic skills example. " * 4)), 1)
    assert not list(tmp_path.rglob("*.pdf"))


def test_save_resume_preserves_existing_file_on_collision(monkeypatch):
    name = uuid4()
    monkeypatch.setattr(storage, "uuid4", lambda: name)
    original = make_pdf("First synthetic profile. " * 4)
    stored = save_resume_file(make_upload(original), 1)
    with pytest.raises(FileExistsError):
        save_resume_file(make_upload(make_pdf("Second synthetic profile. " * 4)), 1)
    assert Path(stored.path).read_bytes() == original


@pytest.fixture(scope="module")
def upload_session_factory():
    try:
        engine = verified_test_engine()
    except ValueError as exc:
        pytest.fail(str(exc), pytrace=False)
    try:
        yield sessionmaker(bind=engine, autoflush=False)
    finally:
        engine.dispose()


@pytest.fixture
def upload_client(upload_session_factory):
    with upload_session_factory() as db:
        user = User(email=f"{uuid4().hex}@example.invalid", hashed_password="unused")
        db.add(user)
        db.commit()
        user_id = user.id
        app = FastAPI()
        app.include_router(resumes.router, prefix="/resumes")
        app.dependency_overrides[get_db] = lambda: db
        app.dependency_overrides[get_active_user] = lambda: SimpleNamespace(id=user_id)
        try:
            with TestClient(app, raise_server_exceptions=False) as client:
                yield client, db, user_id
        finally:
            db.rollback()
            db.query(Resume).filter_by(user_id=user_id).delete()
            db.query(User).filter_by(id=user_id).delete()
            db.commit()


@pytest.mark.parametrize(
    "failure",
    ["none", "insert", "before_commit", "after_commit", "disconnect", "disconnect_no_row", "refresh"],
)
def test_upload_persistence(failure, upload_client, upload_session_factory, monkeypatch, tmp_path):
    client, db, user_id = upload_client
    data = make_pdf("Synthetic technical profile. " * 4)
    # PostgreSQL rejects a filename wider than the existing VARCHAR(255).
    filename = ("a" * 256 if failure == "insert" else "synthetic") + ".pdf"
    commit = db.commit

    def interrupt(*_):
        if failure in ("after_commit", "disconnect"):
            commit()
        if failure in ("disconnect", "disconnect_no_row"):
            raise OperationalError(None, None, OSError(), connection_invalidated=True)
        raise RuntimeError("simulated interruption")

    with monkeypatch.context() as patch:
        if failure in ("before_commit", "after_commit", "disconnect", "disconnect_no_row"):
            patch.setattr(db, "commit", interrupt)
        elif failure == "refresh":
            patch.setattr(db, "refresh", interrupt)
        response = client.post(
            "/resumes/upload", files={"file": (filename, data, "application/pdf")}
        )

    assert response.status_code == (201 if failure == "none" else 500)
    with upload_session_factory() as observer:
        rows = observer.scalars(select(Resume).where(Resume.user_id == user_id)).all()
        if failure in ("insert", "before_commit"):
            assert not rows
            assert not list(tmp_path.rglob("*.pdf"))
            return
        if failure == "disconnect_no_row":
            assert not rows
            pdfs = list(tmp_path.rglob("*.pdf"))
            assert len(pdfs) == 1
            assert pdfs[0].read_bytes() == data
            return
        row, = rows
        assert Path(row.file_path).read_bytes() == data
        fetched = client.get(f"/resumes/{row.id}")
        assert fetched.status_code == 200
        if failure == "none":
            assert response.json() == fetched.json()
            assert response.json()["filename"] == filename
            assert response.json()["status"] == "uploaded"
            assert response.json()["is_active"] is False


@pytest.mark.parametrize(
    ("upload", "expected_status", "expected_detail"),
    [
        (
            make_upload(b"not a pdf"),
            400,
            "El archivo no contiene un PDF válido.",
        ),
        (
            make_upload(b"%PDF-not-a-valid-document"),
            400,
            "El PDF está protegido o no se puede leer.",
        ),
        (
            make_upload(make_pdf("")),
            400,
            "No se ha podido extraer suficiente texto del PDF.",
        ),
        (
            make_upload(b"PK\x03\x04fake-docx", filename="cv.docx"),
            400,
            "Tipo de archivo no permitido. Sube un PDF.",
        ),
        (
            make_upload(
                make_pdf("Contenido profesional suficiente para analizar " * 5),
                content_type="text/plain",
            ),
            400,
            "Tipo de archivo no permitido. Sube un PDF.",
        ),
    ],
)
def test_save_resume_rejects_unsafe_files(
    upload: UploadFile,
    expected_status: int,
    expected_detail: str,
) -> None:
    with pytest.raises(HTTPException) as exc_info:
        save_resume_file(upload, user_id=1)

    assert exc_info.value.status_code == expected_status
    assert exc_info.value.detail == expected_detail


def test_save_resume_rejects_protected_pdf() -> None:
    with pytest.raises(HTTPException) as exc_info:
        save_resume_file(make_upload(make_protected_pdf()), user_id=1)

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "El PDF está protegido o no se puede leer."


def test_save_resume_rejects_oversized_pdf(monkeypatch) -> None:
    monkeypatch.setattr(settings, "MAX_UPLOAD_SIZE_MB", 1)

    with pytest.raises(HTTPException) as exc_info:
        save_resume_file(make_upload(b"%PDF-" + b"x" * (1024 * 1024)), user_id=1)

    assert exc_info.value.status_code == 413
    assert exc_info.value.detail == "El CV supera el tamaño máximo de 1 MB."


def test_save_resume_rejects_pdf_with_too_many_pages(monkeypatch) -> None:
    monkeypatch.setattr(settings, "RESUME_MAX_PAGES", 1)

    with pytest.raises(HTTPException) as exc_info:
        save_resume_file(
            make_upload(
                make_pdf(
                    "Contenido profesional suficiente para validar el documento " * 4,
                    pages=2,
                )
            ),
            user_id=1,
        )

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "El PDF supera el máximo de 1 páginas."


class ProcessorSession:
    def __init__(self) -> None:
        self.commits = 0
        self.added = []
        self.refreshed = []
        self.deactivated_previous_active = False

    def commit(self) -> None:
        self.commits += 1

    def add(self, item) -> None:
        self.added.append(item)

    def refresh(self, item) -> None:
        self.refreshed.append(item)

    def query(self, _model):
        return ProcessorQuery(self)


class ProcessorQuery:
    def __init__(self, db: ProcessorSession) -> None:
        self.db = db

    def filter(self, *_conditions):
        return self

    def update(self, values, *, synchronize_session=False):
        self.db.deactivated_previous_active = values == {"is_active": False}
        return 1


def resume_for_processing(*, is_active: bool = False) -> Resume:
    return Resume(
        id=10,
        user_id=20,
        filename="cv.pdf",
        file_path="/tmp/cv.pdf",
        file_type=".pdf",
        status=ResumeStatus.UPLOADED,
        is_active=is_active,
    )


def profile_payload() -> dict:
    return {
        "profile_type": "Full Stack Developer",
        "summary": "Perfil tecnico detectado.",
        "experience_years": 2.0,
        "education": {"raw": []},
        "languages": ["Ingles"],
        "technologies": ["Python", "FastAPI"],
        "analysis": {},
    }


def test_process_resume_activates_only_after_success(monkeypatch) -> None:
    db = ProcessorSession()
    resume = resume_for_processing()
    monkeypatch.setattr(
        processor,
        "extract_text_from_file",
        lambda *_args, **_kwargs: "Python FastAPI Angular PostgreSQL Docker " * 3,
    )
    monkeypatch.setattr(processor, "build_profile_from_text", lambda _text: profile_payload())
    monkeypatch.setattr(processor, "ensure_profile_embedding", lambda *_args, **_kwargs: None)

    profile = process_resume(db, resume)

    assert profile.profile_type == "Full Stack Developer"
    assert resume.status == ResumeStatus.PROCESSED
    assert resume.is_active is True
    assert resume.processed_at is not None
    assert db.deactivated_previous_active is True


def test_process_resume_validation_failure_marks_resume_failed(monkeypatch) -> None:
    db = ProcessorSession()
    resume = resume_for_processing(is_active=True)
    monkeypatch.setattr(
        processor,
        "extract_text_from_file",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            CvValidationError("No se ha podido extraer suficiente texto del PDF.")
        ),
    )

    with pytest.raises(ResumeProcessingError) as exc_info:
        process_resume(db, resume)

    assert exc_info.value.status_code == 400
    assert exc_info.value.public_message == "No se ha podido extraer suficiente texto del PDF."
    assert resume.status == ResumeStatus.FAILED
    assert resume.is_active is False
    assert resume.processed_at is not None


def test_process_resume_internal_failure_returns_safe_error(monkeypatch) -> None:
    db = ProcessorSession()
    resume = resume_for_processing(is_active=True)
    monkeypatch.setattr(
        processor,
        "extract_text_from_file",
        lambda *_args, **_kwargs: "Python FastAPI Angular PostgreSQL Docker " * 3,
    )
    monkeypatch.setattr(
        processor,
        "build_profile_from_text",
        lambda _text: (_ for _ in ()).throw(RuntimeError("private cv text")),
    )

    with pytest.raises(ResumeProcessingError) as exc_info:
        process_resume(db, resume)

    assert exc_info.value.status_code == 500
    assert exc_info.value.public_message == "No se ha podido procesar el CV en este momento."
    assert "private cv text" not in exc_info.value.public_message
    assert resume.status == ResumeStatus.FAILED
    assert resume.is_active is False
    assert resume.processed_at is not None
