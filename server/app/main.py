from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from time import perf_counter
from uuid import uuid4

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from starlette.responses import Response

from app.api import api_router
from app.common import register_error_handlers
from app.config import get_settings
from app.database import close_database, init_database
from app.observability import configure_logging
from app.security import limiter, rate_limit_exceeded_handler


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
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
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

        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > settings.max_request_body_bytes:
            return JSONResponse(
                status_code=413,
                content={
                    "status_code": 413,
                    "error": "Payload Too Large",
                    "message": "Request body exceeds max allowed size",
                    "path": request.url.path,
                },
            )

        started = perf_counter()
        try:
            response = await call_next(request)
        finally:
            structlog.contextvars.clear_contextvars()

        duration_ms = round((perf_counter() - started) * 1000, 2)

        response.headers["X-Request-ID"] = request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Content-Security-Policy"] = "default-src 'self'"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        logger.info(
            "request.completed",
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration_ms=duration_ms,
            headers=dict(request.headers),
        )
        return response

    register_error_handlers(app)

    return app


app = create_app()
