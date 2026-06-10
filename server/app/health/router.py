from fastapi import APIRouter

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/live", summary="Liveness probe")
async def live() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/number", summary="Validation probe")
async def number(value: int) -> dict[str, int]:
    return {"value": value}
