from fastapi import APIRouter, Request

from app.common.schemas import ErrorEnvelope, LoginProbeResponse
from app.security.rate_limit import limiter

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/login",
    summary="Auth rate-limit probe",
    description=(
        "Returns a deterministic success payload and is rate-limited for security baseline checks."
    ),
    response_model=LoginProbeResponse,
    responses={
        200: {
            "description": "Auth probe completed successfully.",
            "content": {
                "application/json": {
                    "example": {"status": "ok"},
                }
            },
        },
        429: {
            "model": ErrorEnvelope,
            "description": "Too many auth attempts in the configured time window.",
            "content": {
                "application/json": {
                    "example": {
                        "status_code": 429,
                        "error": "Too Many Requests",
                        "message": "Rate limit exceeded",
                        "path": "/api/v1/auth/login",
                    }
                }
            },
        },
    },
)
@limiter.limit("60/minute")
async def login_probe(request: Request) -> LoginProbeResponse:
    _ = request
    return LoginProbeResponse(status="ok")
