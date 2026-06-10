from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ErrorEnvelope(BaseModel):
    status_code: int = Field(examples=[404])
    error: str = Field(examples=["Not Found"])
    message: str = Field(examples=["Not Found"])
    path: str = Field(examples=["/api/v1/health/live"])
    timestamp: datetime | None = None
    request_id: str | None = None
    details: Any | None = None


class LoginProbeResponse(BaseModel):
    status: str = Field(examples=["ok"])


class LiveResponse(BaseModel):
    status: str = Field(examples=["ok"])


class NumberResponse(BaseModel):
    value: int = Field(examples=[42])


class ReadyChecks(BaseModel):
    mongo: bool
    disk: bool
    memory: bool


class ReadyResponse(BaseModel):
    status: str = Field(examples=["ready"])
    checks: ReadyChecks
    disk_free_mb: int = Field(examples=[1024])
    memory_available_mb: int = Field(examples=[2048])

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "status": "ready",
                    "checks": {"mongo": True, "disk": True, "memory": True},
                    "disk_free_mb": 1024,
                    "memory_available_mb": 2048,
                }
            ]
        }
    )
