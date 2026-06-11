from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from time import perf_counter
from typing import Any, cast
from uuid import uuid4

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from starlette.responses import Response

from app.ai.observability import configure_langsmith
from app.api import api_router
from app.common import register_error_handlers
from app.config import get_settings
from app.database import close_database, init_database
from app.lifecycle import ShutdownCoordinator, noop_job_drain
from app.observability import configure_logging, configure_otel, configure_sentry
from app.security import limiter, rate_limit_exceeded_handler
from app.spa import mount_spa

OPENAPI_TAGS = [
    {
        "name": "health",
        "description": "Liveness and readiness probes used by local and deployment health checks.",
    },
    {
        "name": "auth",
        "description": "Authentication endpoints and auth-related security limits.",
    },
    {
        "name": "users",
        "description": "User profile and account-related endpoints.",
    },
    {
        "name": "resumes",
        "description": "Resume CRUD, upload, and management endpoints.",
    },
    {
        "name": "analyses",
        "description": "Resume analysis pipeline endpoints.",
    },
    {
        "name": "notifications",
        "description": "In-app bell notifications for analysis lifecycle events.",
    },
    {
        "name": "admin",
        "description": "Admin-only platform management endpoints.",
    },
]


# Content-Security-Policy for the single-server SPA (issue #98). The inline
# theme-bootstrap script in frontend/index.html is allow-listed by hash (not
# 'unsafe-inline'); a drift test recomputes it. Google Fonts are allow-listed;
# dynamic inline style attributes require 'unsafe-inline' for styles only.
INLINE_THEME_SCRIPT_HASH = "sha256-6QQKaqspGAK5OMrP0ZhE8K74AJ50QGc0G9LHbWPwgW8="
CONTENT_SECURITY_POLICY = "; ".join(
    [
        "default-src 'self'",
        f"script-src 'self' '{INLINE_THEME_SCRIPT_HASH}'",
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
        "font-src 'self' https://fonts.gstatic.com",
        "img-src 'self' data:",
        "connect-src 'self'",
        "object-src 'none'",
        "base-uri 'self'",
        "frame-ancestors 'none'",
        "form-action 'self'",
    ]
)


def _remaining_timeout_seconds(deadline: float) -> float:
    remaining = deadline - perf_counter()
    return max(remaining, 0.0)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    shutdown_timeout_seconds = settings.shutdown_timeout_ms / 1000
    coordinator = ShutdownCoordinator()
    app.state.shutdown_coordinator = coordinator
    app.state.job_runner_drain_hook = noop_job_drain

    configure_logging(settings.log_level, settings.environment)
    configure_sentry(settings)
    configure_langsmith(settings)
    await init_database(settings)
    try:
        yield
    finally:
        shutdown_logger = structlog.get_logger("app.shutdown")
        await coordinator.begin_shutdown()

        deadline = perf_counter() + shutdown_timeout_seconds
        drain_hook: Callable[[float], Awaitable[None]] = app.state.job_runner_drain_hook

        remaining_for_jobs = _remaining_timeout_seconds(deadline)
        await drain_hook(remaining_for_jobs)

        remaining_for_requests = _remaining_timeout_seconds(deadline)
        drained = await coordinator.wait_for_drain(remaining_for_requests)
        if not drained:
            shutdown_logger.warning(
                "shutdown.request_drain_timeout",
                timeout_ms=settings.shutdown_timeout_ms,
            )

        await close_database()


def create_app() -> FastAPI:
    settings = get_settings()
    docs_enabled = settings.is_swagger_enabled
    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/api/docs" if docs_enabled else None,
        redoc_url="/api/redoc" if docs_enabled else None,
        openapi_url="/api/openapi.json" if docs_enabled else None,
        openapi_tags=OPENAPI_TAGS,
    )
    app.state.shutdown_coordinator = ShutdownCoordinator()
    app.state.job_runner_drain_hook = noop_job_drain
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

    if docs_enabled:

        def custom_openapi() -> dict[str, object]:
            if app.openapi_schema is not None:
                return app.openapi_schema

            openapi_schema = get_openapi(
                title=settings.app_name,
                version="0.1.0",
                description="CVantage API",
                routes=app.routes,
                tags=app.openapi_tags,
            )
            components = openapi_schema.setdefault("components", {})
            security_schemes = components.setdefault("securitySchemes", {})
            if isinstance(security_schemes, dict):
                security_schemes.setdefault(
                    "BearerAuth",
                    {
                        "type": "http",
                        "scheme": "bearer",
                        "bearerFormat": "JWT",
                    },
                )
                security_schemes.setdefault(
                    "SessionCookie",
                    {
                        "type": "apiKey",
                        "in": "cookie",
                        "name": "refresh_token",
                    },
                )

            app.openapi_schema = openapi_schema
            return app.openapi_schema

        cast(Any, app).openapi = custom_openapi

    logger = structlog.get_logger("app.requests")

    @app.middleware("http")
    async def request_context_middleware(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        coordinator: ShutdownCoordinator = app.state.shutdown_coordinator
        request_id = request.headers.get("x-request-id", str(uuid4()))
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)

        request_started = await coordinator.try_start_request()
        if not request_started:
            structlog.contextvars.clear_contextvars()
            return JSONResponse(
                status_code=503,
                content={
                    "status_code": 503,
                    "error": "Service Unavailable",
                    "message": "Server is shutting down",
                    "path": request.url.path,
                },
            )

        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > settings.max_request_body_bytes:
            await coordinator.finish_request()
            structlog.contextvars.clear_contextvars()
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
            await coordinator.finish_request()
            structlog.contextvars.clear_contextvars()

        duration_ms = round((perf_counter() - started) * 1000, 2)

        response.headers["X-Request-ID"] = request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Content-Security-Policy"] = CONTENT_SECURITY_POLICY
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        # HSTS only in production (HTTPS) — avoids pinning HTTP dev/test to TLS.
        if settings.environment == "production":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
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
    configure_otel(app, settings)

    if settings.is_spa_enabled:
        from pathlib import Path

        mount_spa(app, Path(settings.spa_dist_dir))

    return app


app = create_app()
