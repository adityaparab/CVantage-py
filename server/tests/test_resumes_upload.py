"""Unit tests for resume upload validation logic (issue #44).

Full HTTP integration tests for the upload endpoint require a running
MongoDB instance. Here we test the validation and deduplication
helper functions as pure unit tests.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import filetype  # type: ignore[import-untyped]
import pytest
from fastapi import HTTPException

from app.database.models import MAX_RESUME_FILE_BYTES
from app.resumes.router import _deduplicate_name, _validate_upload

# PDF magic bytes header
_VALID_PDF = b"%PDF-1.4\nsome content here\n%%EOF"
# DOCX/DOC magic (ZIP PK\x03\x04 header with proper ZIP structure)
_VALID_DOCX = (
    b"PK\x03\x04\x14\x00\x00\x00\x00\x00\x00\x00\x00\x00"
    b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
    b"\x0b\x00\x00\x00[Content_Types].xml\x00PK\x01\x02"
)
# DOC (older format - OLE2 magic bytes D0\xCF\x11\xE0)
_VALID_DOC = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"\x00" * 20


def _make_upload(filename: str, data: bytes, content_type: str) -> MagicMock:
    """Helper to create a mock UploadFile."""
    mock = MagicMock()
    mock.filename = filename
    mock.content_type = content_type
    return mock


class TestValidateUpload:
    def test_pdf_accepted(self) -> None:
        upload = _make_upload("resume.pdf", _VALID_PDF, "application/pdf")
        _validate_upload(upload, _VALID_PDF)  # should not raise

    def test_docx_accepted(self) -> None:
        upload = _make_upload(
            "resume.docx",
            _VALID_DOCX,
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
        _validate_upload(upload, _VALID_DOCX)

    @pytest.mark.skipif(
        filetype.guess(_VALID_DOC) is None,
        reason="OLE2 detection may not work in all environments",
    )
    def test_doc_accepted(self) -> None:
        upload = _make_upload("resume.doc", _VALID_DOC, "application/msword")
        _validate_upload(upload, _VALID_DOC)

    def test_wrong_extension_rejected(self) -> None:
        upload = _make_upload("resume.exe", _VALID_PDF, "application/pdf")
        with pytest.raises(HTTPException) as exc:
            _validate_upload(upload, _VALID_PDF)
        assert exc.value.status_code == 422

    def test_wrong_mime_rejected(self) -> None:
        upload = _make_upload("resume.pdf", _VALID_PDF, "text/plain")
        with pytest.raises(HTTPException) as exc:
            _validate_upload(upload, _VALID_PDF)
        assert exc.value.status_code == 422

    def test_wrong_magic_bytes_rejected(self) -> None:
        data = b"not a pdf at all but has .pdf extension"
        upload = _make_upload("resume.pdf", data, "application/pdf")
        with pytest.raises(HTTPException) as exc:
            _validate_upload(upload, data)
        assert exc.value.status_code == 422

    def test_too_large_rejected(self) -> None:
        data = b"x" * (MAX_RESUME_FILE_BYTES + 1)
        upload = _make_upload("resume.pdf", data, "application/pdf")
        with pytest.raises(HTTPException) as exc:
            _validate_upload(upload, data)
        assert exc.value.status_code == 413

    def test_no_filename_rejected(self) -> None:
        upload = _make_upload("", _VALID_PDF, "application/pdf")
        with pytest.raises(HTTPException) as exc:
            _validate_upload(upload, _VALID_PDF)
        assert exc.value.status_code == 422

    def test_unknown_extension_rejected(self) -> None:
        upload = _make_upload("resume.xyz", _VALID_PDF, "application/pdf")
        with pytest.raises(HTTPException) as exc:
            _validate_upload(upload, _VALID_PDF)
        assert exc.value.status_code == 422


class TestDeduplicateName:
    def test_no_conflict(self) -> None:
        assert _deduplicate_name("resume.pdf", {"other.pdf"}) == "resume.pdf"

    def test_first_conflict(self) -> None:
        assert _deduplicate_name("resume.pdf", {"resume.pdf"}) == "resume (1).pdf"

    def test_multiple_conflicts(self) -> None:
        existing = {"resume.pdf", "resume (1).pdf", "resume (2).pdf"}
        assert _deduplicate_name("resume.pdf", existing) == "resume (3).pdf"

    def test_no_ext(self) -> None:
        assert _deduplicate_name("resume", {"resume"}) == "resume (1)"

    def test_same_stem_diff_ext(self) -> None:
        existing = {"resume.pdf", "resume.docx"}
        assert _deduplicate_name("resume.pdf", existing) == "resume (1).pdf"
