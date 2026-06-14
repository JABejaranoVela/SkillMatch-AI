from urllib.parse import urlsplit

from fastapi import status
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.types import ASGIApp

from app.core.config import Settings, settings


WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


class AuthenticatedOriginMiddleware:
    def __init__(self, app: ASGIApp, app_settings: Settings | None = None) -> None:
        self.app = app
        selected_settings = app_settings or settings
        self.session_cookie_name = selected_settings.SESSION_COOKIE_NAME
        self.allowed_origins = {
            _normalize_origin(selected_settings.FRONTEND_URL),
            *(
                _normalize_origin(origin)
                for origin in selected_settings.BACKEND_CORS_ORIGINS
            ),
        }

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request = Request(scope)
        if (
            request.method in WRITE_METHODS
            and self.session_cookie_name in request.cookies
            and not self._origin_is_allowed(request.headers.get("origin"))
        ):
            response = JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={"detail": "Origen de la solicitud no permitido"},
            )
            await response(scope, receive, send)
            return

        await self.app(scope, receive, send)

    def _origin_is_allowed(self, origin: str | None) -> bool:
        if not origin:
            return False
        try:
            normalized = _normalize_origin(origin)
        except ValueError:
            return False
        return normalized in self.allowed_origins


def _normalize_origin(value: str) -> str:
    parsed = urlsplit(value.strip())
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.netloc
        or parsed.path not in {"", "/"}
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("Invalid origin")
    return f"{parsed.scheme.lower()}://{parsed.netloc.lower()}"
