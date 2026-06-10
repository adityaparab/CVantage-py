from collections.abc import Mapping
from shutil import disk_usage
from typing import Annotated

import psutil
from fastapi import APIRouter, Depends, HTTPException

from app.config import Settings, get_settings
from app.database.client import get_mongo_client

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/live", summary="Liveness probe")
async def live() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/number", summary="Validation probe")
async def number(value: int) -> dict[str, int]:
    return {"value": value}


def get_disk_free_mb() -> int:
    return int(disk_usage("/").free // (1024 * 1024))


def get_memory_available_mb() -> int:
    return int(psutil.virtual_memory().available // (1024 * 1024))


@router.get("/ready", summary="Readiness probe")
async def ready(
    settings: Annotated[Settings, Depends(get_settings)],
) -> Mapping[str, object]:
    checks: dict[str, bool] = {
        "mongo": False,
        "disk": False,
        "memory": False,
    }

    client = get_mongo_client()
    if client is not None:
        try:
            await client.admin.command("ping")
            checks["mongo"] = True
        except Exception:
            checks["mongo"] = False

    disk_free_mb = get_disk_free_mb()
    checks["disk"] = disk_free_mb >= settings.ready_min_disk_free_mb

    memory_available_mb = get_memory_available_mb()
    checks["memory"] = memory_available_mb >= settings.ready_min_memory_available_mb

    payload: dict[str, object] = {
        "status": "ready" if all(checks.values()) else "not_ready",
        "checks": checks,
        "disk_free_mb": disk_free_mb,
        "memory_available_mb": memory_available_mb,
    }

    if all(checks.values()):
        return payload

    raise HTTPException(status_code=503, detail=payload)
