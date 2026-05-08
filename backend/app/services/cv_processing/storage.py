from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException, UploadFile

from app.core.config import settings


@dataclass(frozen=True)
class StoredResume:
    original_filename: str
    path: str
    extension: str


def save_resume_file(file: UploadFile, user_id: int) -> StoredResume:
    original_filename = file.filename or "resume"
    extension = Path(original_filename).suffix.lower()
    if extension not in settings.ALLOWED_RESUME_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Formato no permitido. Usa PDF o DOCX")

    user_dir = Path(settings.UPLOAD_DIR) / str(user_id)
    user_dir.mkdir(parents=True, exist_ok=True)
    destination = user_dir / f"{uuid4().hex}{extension}"

    size = 0
    max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    with destination.open("wb") as output:
        while chunk := file.file.read(1024 * 1024):
            size += len(chunk)
            if size > max_bytes:
                destination.unlink(missing_ok=True)
                raise HTTPException(status_code=413, detail="El CV supera el tamano maximo")
            output.write(chunk)

    return StoredResume(
        original_filename=original_filename,
        path=str(destination),
        extension=extension,
    )

