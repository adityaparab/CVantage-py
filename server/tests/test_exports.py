"""Tests for the resume export service (issue #90)."""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from beanie import PydanticObjectId
from httpx import ASGITransport, AsyncClient

from app.auth.dependencies import get_current_user
from app.database.models import JsonResume, Resume, ResumeSource
from app.exports.docx_export import render_docx
from app.exports.pdf_export import render_pdf
from app.main import create_app

_SAMPLE = {
    "basics": {"name": "Ada Lovelace", "label": "Engineer", "email": "ada@x.io", "summary": "Hi"},
    "work": [
        {
            "name": "Acme",
            "position": "Engineer",
            "startDate": "2022",
            "endDate": "2024",
            "highlights": ["Shipped X"],
        }
    ],
    "education": [{"institution": "MIT", "area": "CS"}],
    "skills": [{"name": "python"}, {"name": "fastapi"}],
    "projects": [{"name": "CVantage", "description": "Resume AI", "highlights": ["Built it"]}],
}


class TestRenderers:
    def test_docx_has_zip_magic(self) -> None:
        data = render_docx("My Resume", _SAMPLE)
        assert data[:2] == b"PK"  # .docx is a zip container
        assert len(data) > 1000

    def test_pdf_has_pdf_magic(self) -> None:
        data = render_pdf("My Resume", _SAMPLE)
        assert data[:5] == b"%PDF-"
        assert len(data) > 500

    def test_renderers_handle_empty_resume(self) -> None:
        assert render_docx("Empty", {})[:2] == b"PK"
        assert render_pdf("Empty", {})[:5] == b"%PDF-"


class _Principal:
    def __init__(self, user_id: PydanticObjectId) -> None:
        self.id = user_id


@pytest_asyncio.fixture
async def export_env(
    beanie_db: object,
) -> AsyncIterator[tuple[AsyncClient, PydanticObjectId]]:
    user_id = PydanticObjectId()

    async def _current_user() -> _Principal:
        return _Principal(user_id)

    app = create_app()
    app.dependency_overrides[get_current_user] = _current_user
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client, user_id


async def _seed_resume(user_id: PydanticObjectId) -> Resume:
    resume = Resume(
        user_id=user_id,
        name="Backend Engineer",
        source=ResumeSource.CREATED,
        json_resume=JsonResume.model_validate(_SAMPLE),
    )
    await resume.insert()
    return resume


@pytest.mark.asyncio
async def test_export_pdf(export_env: tuple[AsyncClient, PydanticObjectId]) -> None:
    client, user_id = export_env
    resume = await _seed_resume(user_id)
    resp = await client.get(f"/api/v1/resumes/{resume.id}/export", params={"format": "pdf"})
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    assert 'filename="Backend_Engineer.pdf"' in resp.headers["content-disposition"]
    assert resp.content[:5] == b"%PDF-"


@pytest.mark.asyncio
async def test_export_docx(export_env: tuple[AsyncClient, PydanticObjectId]) -> None:
    client, user_id = export_env
    resume = await _seed_resume(user_id)
    resp = await client.get(f"/api/v1/resumes/{resume.id}/export", params={"format": "docx"})
    assert resp.status_code == 200
    assert "wordprocessingml" in resp.headers["content-type"]
    assert resp.content[:2] == b"PK"


@pytest.mark.asyncio
async def test_export_foreign_resume_404(
    export_env: tuple[AsyncClient, PydanticObjectId],
) -> None:
    client, _ = export_env
    other = await _seed_resume(PydanticObjectId())
    resp = await client.get(f"/api/v1/resumes/{other.id}/export")
    assert resp.status_code == 404
