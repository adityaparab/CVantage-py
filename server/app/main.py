from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api import api_router
from app.config import get_settings
from app.database import close_database, init_database


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    await init_database(settings)
    try:
        yield
    finally:
        await close_database()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, lifespan=lifespan)
    app.include_router(api_router)

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
