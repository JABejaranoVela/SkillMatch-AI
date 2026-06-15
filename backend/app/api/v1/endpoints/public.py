from pathlib import Path

from fastapi import APIRouter, HTTPException, Request, UploadFile, status

from app.core.config import settings
from app.schemas.public import PublicDemoAnalysisRead
from app.services.auth.rate_limits import client_ip_identifier, consume_rate_limit
from app.services.cv_processing.demo_analyzer import (
    DemoCvValidationError,
    analyze_demo_pdf,
)

router = APIRouter()


@router.post("/demo/analyze-cv", response_model=PublicDemoAnalysisRead)
async def analyze_public_demo_cv(
    request: Request,
    file: UploadFile,
) -> PublicDemoAnalysisRead:
    rate_limit = consume_rate_limit(
        action="public_demo_analyze_cv",
        identifiers=[client_ip_identifier(request)],
        limit=settings.PUBLIC_DEMO_RATE_LIMIT_PER_HOUR,
        window_seconds=3600,
    )
    if not rate_limit.allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Has alcanzado el límite temporal de análisis",
            headers={"Retry-After": str(rate_limit.retry_after)},
        )

    filename = file.filename or ""
    if Path(filename).suffix.lower() != ".pdf":
        await file.close()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El archivo debe ser un PDF",
        )

    try:
        data = await _read_upload_with_limit(file)
        if not data.startswith(b"%PDF-"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El archivo no contiene un PDF válido",
            )
        return analyze_demo_pdf(data)
    except DemoCvValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No se ha podido analizar el CV en este momento",
        ) from exc
    finally:
        await file.close()


async def _read_upload_with_limit(file: UploadFile) -> bytes:
    max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    data = bytearray()
    while chunk := await file.read(1024 * 1024):
        data.extend(chunk)
        if len(data) > max_bytes:
            raise HTTPException(
                status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                detail=f"El PDF supera el máximo de {settings.MAX_UPLOAD_SIZE_MB} MB",
            )
    return bytes(data)
