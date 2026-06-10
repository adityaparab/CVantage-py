from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from time import perf_counter
from uuid import uuid4

import structlog
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.responses import Response

from app.api import api_router
from app.config import get_settings
from app.database import close_database, init_database
from app.observability import configure_logging


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    configure_logging(settings.log_level, settings.environment)
    await init_database(settings)
    try:
        yield
    finally:
        await close_database()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, lifespan=lifespan)
    app.include_router(api_router)
    logger = structlog.get_logger("app.requests")

    @app.middleware("http")
    async def request_context_middleware(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        request_id = request.headers.get("x-request-id", str(uuid4()))
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)

        started = perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            duration_ms = round((perf_counter() - started) * 1000, 2)
            logger.exception(
                "request.error",
                method=request.method,
                path=request.url.path,
                duration_ms=duration_ms,
                headers=dict(request.headers),
            )
            raise
        finally:
            structlog.contextvars.clear_contextvars()

        duration_ms = round((perf_counter() - started) * 1000, 2)

        response.headers["X-Request-ID"] = request_id
        logger.info(
            "request.completed",
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration_ms=duration_ms,
            headers=dict(request.headers),
        )
        return response

    @app.exception_handler(404)
    async def not_found_handler(request: Request, _: Exception) -> JSONResponse:
        if request.url.path.startswith("/api/v1"):
            return JSONResponse(
                status_code=404,
                content={
                    "status_code": 404,
                    "error": "Not Found",
                    "message": "Resource not found",
                    "path": request.url.path,
                    "timestamp": datetime.now(UTC).isoformat(),
                },
            )
        return JSONResponse(status_code=404, content={"detail": "Not Found"})

    return app


app = create_app()
