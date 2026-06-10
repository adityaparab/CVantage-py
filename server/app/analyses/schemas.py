"""Pydantic schemas for the analyses module (issue #52)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class CreateAnalysisRequest(BaseModel):
    """Request to create a new analysis job."""

    name: str = Field(..., min_length=1, max_length=200, examples=["Senior Dev JD Review"])
    job_description: str = Field(
        ...,
        min_length=30,
        max_length=50_000,
        examples=[
            "We are looking for a senior software engineer with 5+ years of experience in Python..."
        ],
    )
    resume_id: str = Field(..., examples=["665c3ef2c9d8f76b6e4f4f20"])

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "Senior Dev JD Review",
                "job_description": "We are looking for a senior software engineer with 5+ years...",
                "resume_id": "665c3ef2c9d8f76b6e4f4f20",
            }
        }
    )


class AnalysisStepResponse(BaseModel):
    """A single step in the 3-step pipeline."""

    key: str
    status: str
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error: str | None = None


class AnalysisResponse(BaseModel):
    """Full analysis response."""

    id: str
    name: str
    resume_id: str
    job_description: str
    status: str
    steps: list[AnalysisStepResponse]
    result: dict[str, object] | None = None
    model_used: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "665c3ef2c9d8f76b6e4f4f30",
                "name": "Senior Dev JD Review",
                "status": "in_progress",
                "steps": [
                    {"key": "compare_resume_jd", "status": "completed"},
                    {"key": "generate_suggestions", "status": "in_progress"},
                    {"key": "prepare_interview_questions", "status": "pending"},
                ],
            }
        }
    )


class AnalysisListItem(BaseModel):
    """Summary item for the paginated analysis list."""

    id: str
    name: str
    resume_id: str
    status: str
    model_used: str | None = None
    created_at: datetime

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "665c3ef2c9d8f76b6e4f4f30",
                "name": "Senior Dev JD Review",
                "status": "completed",
                "created_at": "2026-06-10T10:00:00Z",
            }
        }
    )


class AnalysisListResponse(BaseModel):
    """Paginated list of analyses."""

    items: list[AnalysisListItem]
    total: int = Field(ge=0)
    skip: int = Field(ge=0)
    limit: int = Field(ge=1, le=100)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "items": [
                    {
                        "id": "665c3ef2c9d8f76b6e4f4f30",
                        "name": "Senior Dev JD Review",
                        "resume_id": "665c3ef2c9d8f76b6e4f4f20",
                        "status": "completed",
                        "created_at": "2026-06-10T10:00:00Z",
                    }
                ],
                "total": 1,
                "skip": 0,
                "limit": 20,
            }
        }
    )
