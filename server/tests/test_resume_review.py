"""Tests for upload-parse status exposure powering the review screen (issue #79)."""

from __future__ import annotations

import pytest
from beanie import PydanticObjectId

from app.database.models import JsonResume, Resume, ResumeSource, UploadParse, UploadParseStatus
from app.resumes.service import _to_resume_response


@pytest.mark.asyncio
async def test_to_response_maps_upload_parse(beanie_db: object) -> None:
    resume = Resume(
        user_id=PydanticObjectId(),
        name="Uploaded",
        source=ResumeSource.UPLOADED,
        original_file={
            "file_name": "resume.pdf",
            "mime_type": "application/pdf",
            "size_bytes": 100,
            "storage_key": "u/abc/resume.pdf",
            "sha256": "a" * 64,
        },
        json_resume=JsonResume.model_validate({"basics": {"name": "Ada"}}),
        original_text="Ada Lovelace\nEngineer\n...",
        upload_parse=UploadParse(status=UploadParseStatus.COMPLETED, model_used="fake/model"),
    )
    resp = _to_resume_response(resume)
    assert resp.upload_parse is not None
    assert resp.upload_parse.status == "completed"
    assert resp.upload_parse.model_used == "fake/model"
    # The original extracted text is exposed for the side-by-side review.
    assert resp.original_text == "Ada Lovelace\nEngineer\n..."


@pytest.mark.asyncio
async def test_to_response_surfaces_failed_parse_error(beanie_db: object) -> None:
    resume = Resume(
        user_id=PydanticObjectId(),
        name="Bad upload",
        source=ResumeSource.UPLOADED,
        original_file={
            "file_name": "resume.pdf",
            "mime_type": "application/pdf",
            "size_bytes": 100,
            "storage_key": "u/abc/resume.pdf",
            "sha256": "a" * 64,
        },
        json_resume=JsonResume.model_validate({}),
        upload_parse=UploadParse(status=UploadParseStatus.FAILED, error="Could not extract text"),
    )
    resp = _to_resume_response(resume)
    assert resp.upload_parse is not None
    assert resp.upload_parse.status == "failed"
    assert resp.upload_parse.error == "Could not extract text"


@pytest.mark.asyncio
async def test_to_response_created_resume_has_no_upload_parse(beanie_db: object) -> None:
    resume = Resume(
        user_id=PydanticObjectId(),
        name="Created",
        source=ResumeSource.CREATED,
        json_resume=JsonResume.model_validate({"basics": {"name": "Ada"}}),
    )
    resp = _to_resume_response(resume)
    assert resp.upload_parse is None
