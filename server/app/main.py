from datetime import UTC, datetime

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api import api_router
from app.config import get_settings


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name)
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
