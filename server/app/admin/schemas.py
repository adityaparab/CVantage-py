"""Pydantic schemas for the admin module (issues #59, #60)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


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


class AdminUserListItem(BaseModel):
    """Row in the admin user table (no resume/analysis content — metadata only)."""

    id: str
    full_name: str = Field(alias="fullName")
    email: EmailStr
    role: str
    status: str
    registration_date: datetime = Field(alias="registrationDate")
    last_active_at: datetime | None = Field(default=None, alias="lastActiveAt")
    resume_count: int = Field(alias="resumeCount", ge=0)
    analysis_count: int = Field(alias="analysisCount", ge=0)

    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "id": "665c3ef2c9d8f76b6e4f4f01",
                "fullName": "Jane Candidate",
                "email": "jane@example.com",
                "role": "candidate",
                "status": "active",
                "registrationDate": "2026-01-15T09:30:00Z",
                "lastActiveAt": "2026-06-10T18:00:00Z",
                "resumeCount": 3,
                "analysisCount": 7,
            }
        },
    )


class AdminUserListResponse(BaseModel):
    """Paginated list of users for the admin console."""

    items: list[AdminUserListItem]
    total: int = Field(ge=0)
    skip: int = Field(ge=0)
    limit: int = Field(ge=1, le=100)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "items": [
                    {
                        "id": "665c3ef2c9d8f76b6e4f4f01",
                        "fullName": "Jane Candidate",
                        "email": "jane@example.com",
                        "role": "candidate",
                        "status": "active",
                        "registrationDate": "2026-01-15T09:30:00Z",
                        "lastActiveAt": "2026-06-10T18:00:00Z",
                        "resumeCount": 3,
                        "analysisCount": 7,
                    }
                ],
                "total": 1,
                "skip": 0,
                "limit": 20,
            }
        }
    )


class AdminUserUpdateRequest(BaseModel):
    """Editable user fields for an admin (full name / email)."""

    full_name: str | None = Field(default=None, alias="fullName", min_length=1, max_length=200)
    email: EmailStr | None = None

    model_config = ConfigDict(populate_by_name=True)


class AdminPasswordResetRequest(BaseModel):
    """Admin password reset — set a temporary password or trigger a reset email."""

    new_password: str | None = Field(
        default=None,
        alias="newPassword",
        min_length=8,
        max_length=200,
        description="If set, used as a temporary password; otherwise a reset email is sent.",
    )

    model_config = ConfigDict(populate_by_name=True)


class AdminPasswordResetResponse(BaseModel):
    status: str = "ok"
    method: str = Field(description="'temp_password' or 'reset_email'")

    model_config = ConfigDict(
        json_schema_extra={"example": {"status": "ok", "method": "reset_email"}}
    )


class AdminActionResponse(BaseModel):
    status: str = "ok"

    model_config = ConfigDict(json_schema_extra={"example": {"status": "ok"}})


class AdminResumeListItem(BaseModel):
    """Resume metadata for admins — explicit whitelist, NEVER content.

    Deliberately excludes ``json_resume`` and ``original_text`` so resume or
    analysis content can never leak through the admin API (PROMPT.md privacy).
    """

    id: str
    name: str
    source: str
    analysis_status: str = Field(alias="analysisStatus")
    analysis_count: int = Field(alias="analysisCount", ge=0)
    created_at: datetime = Field(alias="createdAt")
    last_analyzed_at: datetime | None = Field(default=None, alias="lastAnalyzedAt")

    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "id": "665c3ef2c9d8f76b6e4f4f20",
                "name": "Backend Engineer Resume",
                "source": "uploaded",
                "analysisStatus": "completed",
                "analysisCount": 4,
                "createdAt": "2026-02-01T12:00:00Z",
                "lastAnalyzedAt": "2026-06-09T08:30:00Z",
            }
        },
    )


class AdminResumeListResponse(BaseModel):
    """A user's resumes (metadata only) for the admin console."""

    items: list[AdminResumeListItem]
    total: int = Field(ge=0)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "items": [
                    {
                        "id": "665c3ef2c9d8f76b6e4f4f20",
                        "name": "Backend Engineer Resume",
                        "source": "uploaded",
                        "analysisStatus": "completed",
                        "analysisCount": 4,
                        "createdAt": "2026-02-01T12:00:00Z",
                        "lastAnalyzedAt": "2026-06-09T08:30:00Z",
                    }
                ],
                "total": 1,
            }
        }
    )
