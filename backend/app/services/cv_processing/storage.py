from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException, UploadFile

from app.core.config import settings
from app.services.cv_processing.extractor import CvValidationError, extract_text_from_pdf_bytes


PDF_MIME_TYPES = {"application/pdf"}
GENERIC_MIME_TYPES = {"", "application/octet-stream", "binary/octet-stream"}


@dataclass(frozen=True)
class StoredResume:
    original_filename: str
    path: str
    extension: str


def save_resume_file(file: UploadFile, user_id: int) -> StoredResume:
    original_filename = file.filename or "resume"
    extension = Path(original_filename).suffix.lower()
    if extension not in settings.ALLOWED_RESUME_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail="Tipo de archivo no permitido. Sube un PDF.",
        )
    content_type = (file.content_type or "").lower()
    if content_type not in PDF_MIME_TYPES | GENERIC_MIME_TYPES:
        raise HTTPException(
            status_code=400,
            detail="Tipo de archivo no permitido. Sube un PDF.",
        )

    data = _read_upload_with_limit(file)
    try:
        extract_text_from_pdf_bytes(
            data,
            max_pages=settings.RESUME_MAX_PAGES,
            min_text_chars=settings.RESUME_MIN_TEXT_CHARS,
        )
    except CvValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    user_dir = Path(settings.UPLOAD_DIR) / str(user_id)
    user_dir.mkdir(parents=True, exist_ok=True)
    destination = user_dir / f"{uuid4().hex}{extension}"

    destination.write_bytes(data)

    return StoredResume(
        original_filename=original_filename,
        path=str(destination),
        extension=extension,
    )


def _read_upload_with_limit(file: UploadFile) -> bytes:
    size = 0
    max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    data = bytearray()
    while chunk := file.file.read(1024 * 1024):
        size += len(chunk)
        if size > max_bytes:
            raise HTTPException(
                status_code=413,
                detail=f"El CV supera el tamaño máximo de {settings.MAX_UPLOAD_SIZE_MB} MB.",
            )
        data.extend(chunk)
    return bytes(data)
