from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address, default_limits=["200/minute"])


def rate_limit_exceeded_handler(request: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, RateLimitExceeded):
        raise exc

    request_id = request.headers.get("x-request-id") or request.headers.get("X-Request-ID")
    payload: dict[str, Any] = {
        "status_code": 429,
        "error": "Too Many Requests",
        "message": "Rate limit exceeded",
        "path": request.url.path,
        "timestamp": datetime.now(UTC).isoformat(),
    }
    if request_id:
        payload["request_id"] = request_id

    return JSONResponse(status_code=429, content=payload)
