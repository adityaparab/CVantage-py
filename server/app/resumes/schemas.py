"""
json-resume Pydantic v2 models for CVantage.

Based on https://jsonresume.org/schema/
All fields are optional per the official schema; prune_empty() removes empty nested structures.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator

# ============================================================================
# Partial Date Support (YYYY, YYYY-MM, or YYYY-MM-DD)
# ============================================================================


class PartialDate(BaseModel):
    """A flexible date that can be year-only, year-month, or full date."""

    year: int | None = Field(None, ge=1900, le=2100)
    month: int | None = Field(None, ge=1, le=12)
    day: int | None = Field(None, ge=1, le=31)

    @model_validator(mode="after")
    def validate_partial_date(self) -> PartialDate:
        if self.year is None:
            return self
        if self.month is not None and self.day is None:
            return self
        if self.month is None and self.day is None:
            return self
        if self.month is None and self.day is not None:
            raise ValueError("If day is provided, month must also be provided")
        return self

    def to_iso_string(self) -> str | None:
        """Convert to ISO 8601 string: YYYY, YYYY-MM, or YYYY-MM-DD."""
        if self.year is None:
            return None
        if self.month is None:
            return str(self.year)
        if self.day is None:
            return f"{self.year:04d}-{self.month:02d}"
        return f"{self.year:04d}-{self.month:02d}-{self.day:02d}"


# ============================================================================
# Core Resume Sections
# ============================================================================


class BasicProfile(BaseModel):
    """Basics section: contact info and headline."""

    name: str | None = None
    label: str | None = None
    image: HttpUrl | None = None
    email: str | None = None
    phone: str | None = None
    url: HttpUrl | None = None
    summary: str | None = None
    location: Location | None = None
    profiles: list[Profile] = Field(default_factory=list)


class Location(BaseModel):
    """Location information."""

    address: str | None = None
    postalCode: str | None = None
    city: str | None = None
    countryCode: str | None = None
    region: str | None = None


class Profile(BaseModel):
    """Social media or professional profile."""

    network: str | None = None
    username: str | None = None
    url: HttpUrl | None = None


class Work(BaseModel):
    """Work experience entry."""

    name: str | None = None
    position: str | None = None
    startDate: PartialDate | None = None
    endDate: PartialDate | None = None
    summary: str | None = None
    highlights: list[str] = Field(default_factory=list)
    url: HttpUrl | None = None
    isCurrentRole: bool = False


class Volunteer(BaseModel):
    """Volunteer experience entry."""

    organization: str | None = None
    position: str | None = None
    startDate: PartialDate | None = None
    endDate: PartialDate | None = None
    summary: str | None = None
    highlights: list[str] = Field(default_factory=list)
    url: HttpUrl | None = None


class Education(BaseModel):
    """Education entry."""

    institution: str | None = None
    studyType: str | None = None
    area: str | None = None
    startDate: PartialDate | None = None
    endDate: PartialDate | None = None
    score: str | None = None
    courses: list[str] = Field(default_factory=list)


class Award(BaseModel):
    """Award or honor received."""

    title: str | None = None
    date: PartialDate | None = None
    awarder: str | None = None
    summary: str | None = None


class Certificate(BaseModel):
    """Professional certification."""

    name: str | None = None
    date: PartialDate | None = None
    issuer: str | None = None
    url: HttpUrl | None = None


class Publication(BaseModel):
    """Published work or article."""

    name: str | None = None
    publisher: str | None = None
    releaseDate: PartialDate | None = None
    website: HttpUrl | None = None
    summary: str | None = None


class Skill(BaseModel):
    """Professional skill."""

    name: str | None = None
    level: str | None = None
    keywords: list[str] = Field(default_factory=list)


class Language(BaseModel):
    """Language proficiency."""

    language: str | None = None
    fluency: str | None = None


class Interest(BaseModel):
    """Personal interest or hobby."""

    name: str | None = None
    keywords: list[str] = Field(default_factory=list)


class Reference(BaseModel):
    """Reference or recommendation."""

    name: str | None = None
    reference: str | None = None


class Project(BaseModel):
    """Personal or professional project."""

    name: str | None = None
    description: str | None = None
    highlights: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    startDate: PartialDate | None = None
    endDate: PartialDate | None = None
    url: HttpUrl | None = None
    roles: list[str] = Field(default_factory=list)
    entity: str | None = None
    type: str | None = None


class Meta(BaseModel):
    """Resume metadata."""

    canonical: HttpUrl | None = None
    version: str | None = None
    lastModified: date | None = None


# ============================================================================
# Full Resume Schema
# ============================================================================


class Resume(BaseModel):
    """Complete json-resume schema with all sections."""

    basics: BasicProfile | None = None
    work: list[Work] = Field(default_factory=list)
    volunteer: list[Volunteer] = Field(default_factory=list)
    education: list[Education] = Field(default_factory=list)
    awards: list[Award] = Field(default_factory=list)
    certificates: list[Certificate] = Field(default_factory=list)
    publications: list[Publication] = Field(default_factory=list)
    skills: list[Skill] = Field(default_factory=list)
    languages: list[Language] = Field(default_factory=list)
    interests: list[Interest] = Field(default_factory=list)
    references: list[Reference] = Field(default_factory=list)
    projects: list[Project] = Field(default_factory=list)
    meta: Meta | None = None


# ============================================================================
# prune_empty Utility
# ============================================================================


def _is_empty_value(value: object) -> bool:
    return value is None or value == "" or value == [] or value == {}


def prune_empty(obj: object) -> object:
    """
    Recursively remove empty strings, lists, dicts, and None values.

    Mirrors Beanie pre-validate behavior to prevent storing placeholder structures.
    - Empty strings → removed
    - Empty lists → removed
    - Empty dicts → removed
    - None → removed (implicitly via filtering)
    - Nested models → recursively pruned, then checked for emptiness
    - Pydantic models → converted to dict, pruned, converted back
    """
    if isinstance(obj, BaseModel):
        obj = obj.model_dump(exclude_none=True, mode="python")

    if isinstance(obj, dict):
        pruned_dict: dict[object, object] = {}
        for key, value in obj.items():
            cleaned = prune_empty(value)
            # Only include non-empty values
            if not _is_empty_value(cleaned):
                pruned_dict[key] = cleaned
        return pruned_dict if pruned_dict else None

    if isinstance(obj, list):
        pruned_list = [prune_empty(item) for item in obj]
        non_empty = [item for item in pruned_list if not _is_empty_value(item)]
        return non_empty if non_empty else None

    if isinstance(obj, str):
        return obj if obj else None

    # For other types (int, bool, date, PartialDate, etc.), return as-is
    return obj


def resume_to_clean_dict(resume: Resume) -> dict[str, Any]:
    """Export resume to dict with all empty structures pruned."""
    data = resume.model_dump(exclude_none=True, mode="python")
    cleaned = prune_empty(data)
    return cleaned if isinstance(cleaned, dict) else {}


# ============================================================================
# CRUD API DTOs (Issue #41 — Resume CRUD)
# ============================================================================


class CreateResumeRequest(BaseModel):
    """Request body for creating a new form-created resume."""

    name: str = Field(..., min_length=1, max_length=200, examples=["My Resume"])
    json_resume: Resume = Field(..., description="The full json-resume document")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "Software Engineer Resume",
                "json_resume": {
                    "basics": {
                        "name": "Jane Doe",
                        "email": "jane@example.com",
                        "label": "Full-Stack Developer",
                    },
                    "skills": [{"name": "Python", "level": "Expert"}],
                },
            }
        }
    )


class UpdateResumeRequest(BaseModel):
    """Request body for updating an existing resume. All fields optional."""

    name: str | None = Field(
        default=None, min_length=1, max_length=200, examples=["Updated Resume"]
    )
    json_resume: Resume | None = Field(default=None, description="Updated json-resume document")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "Senior Engineer Resume",
                "json_resume": {
                    "basics": {
                        "name": "Jane Doe",
                        "label": "Senior Full-Stack Developer",
                    },
                },
            }
        }
    )


class ResumeResponse(BaseModel):
    """Full resume response returned by get/create/update endpoints."""

    id: str = Field(examples=["665c3ef2c9d8f76b6e4f4f20"])
    name: str = Field(examples=["My Resume"])
    source: str = Field(examples=["created"])
    json_resume: Resume = Field(description="The full json-resume document")
    analysis_status: str = Field(examples=["unanalyzed"])
    original_text: str | None = Field(
        default=None, description="Raw extracted text (uploaded resumes only)"
    )
    last_analyzed_at: datetime | None = Field(default=None, examples=["2026-06-10T12:00:00Z"])
    analysis_count: int = Field(ge=0, examples=[0])
    created_at: datetime = Field(examples=["2026-06-10T10:00:00Z"])
    updated_at: datetime = Field(examples=["2026-06-10T10:30:00Z"])

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "665c3ef2c9d8f76b6e4f4f20",
                "name": "Software Engineer Resume",
                "source": "created",
                "json_resume": {
                    "basics": {"name": "Jane Doe", "email": "jane@example.com"},
                },
                "analysis_status": "unanalyzed",
                "original_text": None,
                "last_analyzed_at": None,
                "analysis_count": 0,
                "created_at": "2026-06-10T10:00:00Z",
                "updated_at": "2026-06-10T10:00:00Z",
            }
        },
    )


class ResumeListItem(BaseModel):
    """Summary item for the paginated resume list."""

    id: str = Field(examples=["665c3ef2c9d8f76b6e4f4f20"])
    name: str = Field(examples=["My Resume"])
    source: str = Field(examples=["created"])
    analysis_status: str = Field(examples=["unanalyzed"])
    last_analyzed_at: datetime | None = Field(default=None, examples=["2026-06-10T12:00:00Z"])
    analysis_count: int = Field(ge=0, examples=[0])
    created_at: datetime = Field(examples=["2026-06-10T10:00:00Z"])

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "665c3ef2c9d8f76b6e4f4f20",
                "name": "Software Engineer Resume",
                "source": "created",
                "analysis_status": "unanalyzed",
                "last_analyzed_at": None,
                "analysis_count": 0,
                "created_at": "2026-06-10T10:00:00Z",
            }
        }
    )


class ResumeListResponse(BaseModel):
    """Paginated list of resumes for the current user."""

    items: list[ResumeListItem]
    total: int = Field(ge=0, examples=[1])
    skip: int = Field(ge=0, examples=[0])
    limit: int = Field(ge=1, le=100, examples=[20])

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "items": [
                    {
                        "id": "665c3ef2c9d8f76b6e4f4f20",
                        "name": "Software Engineer Resume",
                        "source": "created",
                        "analysis_status": "unanalyzed",
                        "last_analyzed_at": None,
                        "analysis_count": 0,
                        "created_at": "2026-06-10T10:00:00Z",
                    }
                ],
                "total": 1,
                "skip": 0,
                "limit": 20,
            }
        }
    )


class DeleteResumeResponse(BaseModel):
    """Response after a successful soft-delete."""

    status: str = Field("ok", examples=["ok"])

    model_config = ConfigDict(json_schema_extra={"example": {"status": "ok"}})
