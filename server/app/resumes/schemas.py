"""
json-resume Pydantic v2 models for CVantage.

Based on https://jsonresume.org/schema/
All fields are optional per the official schema; prune_empty() removes empty nested structures.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from pydantic import BaseModel, Field, HttpUrl, model_validator

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
