from fastapi import APIRouter, Request

from app.security.rate_limit import limiter

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", summary="Auth rate-limit probe")
@limiter.limit("60/minute")
async def login_probe(request: Request) -> dict[str, str]:
    _ = request
    return {"status": "ok"}
