from io import BytesIO
from pathlib import Path

import fitz
from fastapi import HTTPException, UploadFile
import pytest
from starlette.datastructures import Headers

from app.core.config import settings
from app.models.resume import Resume, ResumeStatus
from app.services.cv_processing import processor
from app.services.cv_processing.extractor import CvValidationError
from app.services.cv_processing.processor import ResumeProcessingError, process_resume
from app.services.cv_processing.storage import save_resume_file


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
