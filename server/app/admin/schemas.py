"""Pydantic schemas for the admin module (issue #59)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class AdminStatsResponse(BaseModel):
    """Platform-wide statistics visible only to admin users."""

    registered_users: int = Field(alias="registeredUsers", ge=0, examples=[42])
    total_resumes: int = Field(alias="totalResumes", ge=0, examples=[128])
    total_analyses: int = Field(alias="totalAnalyses", ge=0, examples=[256])

    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "registeredUsers": 42,
                "totalResumes": 128,
                "totalAnalyses": 256,
            }
        },
    )
