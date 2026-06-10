from __future__ import annotations

from datetime import UTC, datetime
from http import HTTPStatus
from typing import Any

import structlog
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = structlog.get_logger("app.errors")


def _error_envelope(
    request: Request,
    status_code: int,
    error: str,
    message: str,
    details: Any | None = None,
) -> dict[str, Any]:
    request_id = request.headers.get("x-request-id") or request.headers.get("X-Request-ID")
    payload: dict[str, Any] = {
        "status_code": status_code,
        "error": error,
        "message": message,
        "path": request.url.path,
        "timestamp": datetime.now(UTC).isoformat(),
    }
    if request_id:
        payload["request_id"] = request_id
    if details is not None:
        payload["details"] = details
    return payload


def _is_api_request(request: Request) -> bool:
    return request.url.path.startswith("/api/v1")


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(
        request: Request,
        exc: StarletteHTTPException,
    ) -> JSONResponse:
        if not _is_api_request(request):
            return JSONResponse(status_code=exc.status_code, content={"detail": str(exc.detail)})

        try:
            error_label = HTTPStatus(exc.status_code).phrase
        except ValueError:
            error_label = "HTTP Error"

        message: str
        details: Any | None
        if isinstance(exc.detail, dict):
            message = str(exc.detail.get("message", error_label))
            details = exc.detail
        else:
            message = str(exc.detail)
            details = None

        return JSONResponse(
            status_code=exc.status_code,
            content=_error_envelope(
                request=request,
                status_code=exc.status_code,
                error=error_label,
                message=message,
                details=details,
            ),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        if not _is_api_request(request):
            return JSONResponse(status_code=422, content={"detail": exc.errors()})

        return JSONResponse(
            status_code=422,
            content=_error_envelope(
                request=request,
                status_code=422,
                error="Validation Error",
                message="Request validation failed",
                details=exc.errors(),
            ),
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        if not _is_api_request(request):
            raise exc

        logger.exception("request.unhandled_exception", path=request.url.path)

        return JSONResponse(
            status_code=500,
            content=_error_envelope(
                request=request,
                status_code=500,
                error="Internal Server Error",
                message="Unexpected server error",
            ),
        )
