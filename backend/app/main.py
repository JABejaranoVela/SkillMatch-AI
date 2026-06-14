import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.request_security import AuthenticatedOriginMiddleware
from app.services.embeddings.semantic import warm_up_embeddings_model

logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.PROJECT_NAME,
        version=settings.PROJECT_VERSION,
        openapi_url=f"{settings.API_V1_PREFIX}/openapi.json",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.BACKEND_CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(AuthenticatedOriginMiddleware)

    @app.on_event("startup")
    def preload_embeddings_model() -> None:
        try:
            warm_up_embeddings_model()
        except Exception as exc:
            logger.warning("No se pudo precargar el modelo de embeddings: %s", exc)

    app.include_router(api_router, prefix=settings.API_V1_PREFIX)
    return app


app = create_app()
