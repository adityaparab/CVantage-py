from shutil import disk_usage
from typing import Annotated

import psutil
from fastapi import APIRouter, Depends, HTTPException, Query

from app.common.schemas import ErrorEnvelope, LiveResponse, NumberResponse, ReadyResponse
from app.config import Settings, get_settings
from app.database.client import get_mongo_client

router = APIRouter(prefix="/health", tags=["health"])


@router.get(
    "/live",
    summary="Liveness probe",
    description="Verifies that the API process is running.",
    response_model=LiveResponse,
    responses={
        200: {
            "description": "The API process is alive.",
            "content": {
                "application/json": {
                    "example": {"status": "ok"},
                }
            },
        }
    },
)
async def live() -> LiveResponse:
    return LiveResponse(status="ok")


@router.get(
    "/number",
    summary="Validation probe",
    description="Echoes a validated integer query parameter.",
    response_model=NumberResponse,
    responses={
        200: {
            "description": "The validated integer value.",
            "content": {
                "application/json": {
                    "example": {"value": 42},
                }
            },
        },
        422: {
            "model": ErrorEnvelope,
            "description": "The provided query parameter failed validation.",
            "content": {
                "application/json": {
                    "example": {
                        "status_code": 422,
                        "error": "Validation Error",
                        "message": "Request validation failed",
                        "path": "/api/v1/health/number",
                    }
                }
            },
        },
    },
)
async def number(
    value: Annotated[
        int,
        Query(description="Integer value to echo", examples=[42]),
    ],
) -> NumberResponse:
    return NumberResponse(value=value)


def get_disk_free_mb() -> int:
    return int(disk_usage("/").free // (1024 * 1024))


def get_memory_available_mb() -> int:
    return int(psutil.virtual_memory().available // (1024 * 1024))


@router.get(
    "/ready",
    summary="Readiness probe",
    description="Checks Mongo connectivity and minimum host resource thresholds.",
    response_model=ReadyResponse,
    responses={
        200: {
            "description": "All readiness checks passed.",
            "content": {
                "application/json": {
                    "example": {
                        "status": "ready",
                        "checks": {"mongo": True, "disk": True, "memory": True},
                        "disk_free_mb": 1024,
                        "memory_available_mb": 2048,
                    }
                }
            },
        },
        503: {
            "model": ErrorEnvelope,
            "description": "One or more readiness checks failed.",
            "content": {
                "application/json": {
                    "example": {
                        "status_code": 503,
                        "error": "Service Unavailable",
                        "message": "Service Unavailable",
                        "path": "/api/v1/health/ready",
                        "details": {
                            "status": "not_ready",
                            "checks": {"mongo": False, "disk": True, "memory": True},
                            "disk_free_mb": 512,
                            "memory_available_mb": 1024,
                        },
                    }
                }
            },
        },
    },
)
async def ready(
    settings: Annotated[Settings, Depends(get_settings)],
) -> ReadyResponse:
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
        return ReadyResponse.model_validate(payload)

    raise HTTPException(status_code=503, detail=payload)
