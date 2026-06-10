"""Tests for json-resume Pydantic schemas (issue #40)."""

from __future__ import annotations

from typing import Any, cast

import pytest
from hypothesis import given
from hypothesis import strategies as st
from pydantic import ValidationError

from app.resumes.schemas import (
    BasicProfile,
    Education,
    Location,
    PartialDate,
    Resume,
    Skill,
    Work,
    prune_empty,
    resume_to_clean_dict,
)


class TestPartialDate:
    """Test PartialDate parsing and validation."""

    def test_year_only(self) -> None:
        pd = PartialDate(year=2024, month=None, day=None)
        assert pd.to_iso_string() == "2024"

    def test_year_month(self) -> None:
        pd = PartialDate(year=2024, month=6, day=None)
        assert pd.to_iso_string() == "2024-06"

    def test_full_date(self) -> None:
        pd = PartialDate(year=2024, month=6, day=10)
        assert pd.to_iso_string() == "2024-06-10"

    def test_day_without_month_invalid(self) -> None:
        with pytest.raises(ValidationError):
            PartialDate(year=2024, month=None, day=10)

    def test_all_none_valid(self) -> None:
        pd = PartialDate(year=None, month=None, day=None)
        assert pd.to_iso_string() is None


class TestBasicProfile:
    """Test basics section."""

    def test_minimal_basics(self) -> None:
        basics = BasicProfile()
        assert basics.name is None
        assert basics.profiles == []

    def test_basics_with_location(self) -> None:
        basics = BasicProfile(
            name="Jane Doe",
            location=Location(city="San Francisco", region="CA"),
        )
        assert basics.name == "Jane Doe"
        assert basics.location is not None
        assert basics.location.city == "San Francisco"


class TestWork:
    """Test work experience entries."""

    def test_minimal_work(self) -> None:
        work = Work()
        assert work.name is None
        assert work.highlights == []
        assert work.isCurrentRole is False

    def test_work_with_dates(self) -> None:
        work = Work(
            name="Tech Company",
            startDate=PartialDate(year=2020, month=None, day=None),
            endDate=PartialDate(year=2024, month=None, day=None),
        )
        assert work.name == "Tech Company"
        assert work.startDate is not None
        assert work.startDate.to_iso_string() == "2020"


class TestResume:
    """Test full resume schema."""

    def test_empty_resume(self) -> None:
        """Empty resume is valid."""
        resume = Resume()
        assert resume.basics is None
        assert resume.work == []

    def test_resume_with_work_history(self) -> None:
        """Resume with work entries."""
        resume = Resume(
            basics=BasicProfile(name="John Doe"),
            work=[
                Work(name="Company A", position="Engineer"),
                Work(name="Company B", position="Lead"),
            ],
        )
        assert len(resume.work) == 2
        assert resume.work[0].name == "Company A"

    def test_canonical_sample_resume(self) -> None:
        """Verify schema accepts a realistic resume structure."""
        resume = Resume(
            basics=BasicProfile(
                name="Richard Hendriks",
                label="Programmer",
                email="richard@example.com",
                phone="+1 650-253-0000",
                summary="Full-stack developer with 5 years of experience",
            ),
            work=[
                Work(
                    name="Piedpiper",
                    position="CEO",
                    startDate=PartialDate(year=2013, month=None, day=None),
                    summary="Implemented a new compression algorithm",
                    highlights=["Increased efficiency by 40%"],
                ),
            ],
            education=[
                Education(
                    institution="Stanford University",
                    studyType="Masters",
                    area="Computer Science",
                    startDate=PartialDate(year=2007, month=None, day=None),
                    endDate=PartialDate(year=2009, month=None, day=None),
                ),
            ],
            skills=[
                Skill(name="Python", level="Expert"),
                Skill(name="JavaScript", level="Intermediate"),
            ],
        )
        assert resume.basics is not None
        assert resume.basics.name == "Richard Hendriks"
        assert len(resume.work) == 1
        assert len(resume.skills) == 2


class TestPruneEmpty:
    """Property-based tests for prune_empty utility."""

    @given(st.text())
    def test_prune_empty_empty_string_removed(self, s: str) -> None:
        """Empty strings are always pruned."""
        if s == "":
            assert prune_empty(s) is None
        else:
            assert prune_empty(s) == s

    @given(st.lists(st.none()))
    def test_prune_empty_list_of_nones(self, items: list[None]) -> None:
        """Lists of None values become empty/None."""
        result = prune_empty(items)
        assert result is None or result == []

    def test_prune_empty_nested_dict(self) -> None:
        """Nested dicts with empty values are pruned."""
        data = {
            "name": "John",
            "middle_name": "",
            "nickname": None,
            "nested": {
                "city": "NYC",
                "state": "",
                "country": None,
            },
        }
        result = prune_empty(data)
        assert result == {
            "name": "John",
            "nested": {"city": "NYC"},
        }

    def test_prune_empty_resume_removes_placeholders(self) -> None:
        """Prune_empty removes empty nested structures from resume."""
        resume = Resume(
            basics=BasicProfile(
                name="Jane Doe",
                email="",  # Will be pruned
                label=None,  # Will be pruned
                profiles=[],  # Will be pruned
            ),
            work=[
                Work(name="Company", position="", highlights=[]),  # Some pruned
            ],
            skills=[],  # Empty list pruned
        )
        cleaned = resume_to_clean_dict(resume)
        assert "email" not in cleaned.get("basics", {})
        assert "label" not in cleaned.get("basics", {})
        assert "skills" not in cleaned


class TestResumeToCleanDict:
    """Test resume export with pruning."""

    def test_export_realistic_resume(self) -> None:
        """Full resume exports cleanly without empty fields."""
        resume = Resume(
            basics=BasicProfile(
                name="Alice Smith",
                email="alice@example.com",
                label="Data Scientist",
            ),
            work=[Work(name="TechCorp", position="Senior DS")],
            education=[Education(institution="MIT", studyType="PhD", area="ML")],
        )
        exported = resume_to_clean_dict(resume)
        assert exported["basics"]["name"] == "Alice Smith"
        assert len(exported["work"]) == 1
        assert len(exported["education"]) == 1
        # No empty arrays in export
        assert "skills" not in exported
        assert "references" not in exported

    def test_export_preserves_boolean_false(self) -> None:
        """Verify False values (like isCurrentRole=False) are preserved."""
        resume = Resume(
            work=[Work(name="Past Company", isCurrentRole=False)],
        )
        exported = resume_to_clean_dict(resume)
        # False should be preserved as it's meaningful
        assert exported["work"][0]["isCurrentRole"] is False


class TestValidation:
    """Test schema validation."""

    def test_invalid_partial_date_range(self) -> None:
        """Invalid date ranges rejected."""
        with pytest.raises(ValidationError):
            PartialDate(year=2024, month=13, day=None)  # Invalid month

    def test_invalid_url_field(self) -> None:
        """Invalid URLs rejected."""
        with pytest.raises(ValidationError):
            BasicProfile(url=cast(Any, "not-a-url"))

    def test_httpurl_optional_fields_valid(self) -> None:
        """HTTP URL fields are optional."""
        basics = BasicProfile(image=None, url=None)
        assert basics.image is None
        assert basics.url is None
