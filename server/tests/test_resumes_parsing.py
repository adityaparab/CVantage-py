"""Tests for the resume parsing pipeline (issue #51)."""

from __future__ import annotations

from app.resumes.parsing import SYSTEM_PROMPT, ParseProgressEvent


class TestParseProgressEvent:
    def test_construction(self) -> None:
        event = ParseProgressEvent(
            resume_id="abc123",
            status="processing",
            model_used="gpt-4o-mini",
        )
        assert event.resume_id == "abc123"
        assert event.status == "processing"
        assert event.model_used == "gpt-4o-mini"

    def test_optional_fields(self) -> None:
        event = ParseProgressEvent(resume_id="x", status="completed")
        assert event.error is None
        assert event.timestamp == ""


class TestSystemPrompt:
    def test_prompt_contains_instructions(self) -> None:
        assert "json-resume" in SYSTEM_PROMPT
        assert "JSON" in SYSTEM_PROMPT
        assert "schema" in SYSTEM_PROMPT

    def test_prompt_has_extraction_rules(self) -> None:
        assert "work experience" in SYSTEM_PROMPT.lower()
        assert "dates" in SYSTEM_PROMPT.lower()


def test_parsing_module_importable() -> None:
    """Verifies the parsing module can be imported."""
    from app.resumes import parsing

    assert hasattr(parsing, "run_parse_job")
    assert hasattr(parsing, "reparse_resume")
    assert hasattr(parsing, "ParseProgressEvent")
