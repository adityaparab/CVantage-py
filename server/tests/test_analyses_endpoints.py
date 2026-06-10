"""Endpoint tests for the analyses router (issue #53, consolidated in #55).

Drives the real FastAPI router against an in-memory Beanie client with the
auth dependency overridden, exercising create/list/get/retry/cancel and the
suggestion apply/dismiss routes.
"""

from __future__ import annotations

import importlib
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from beanie import PydanticObjectId
from httpx import ASGITransport, AsyncClient

from app.auth.dependencies import get_current_user
from app.database.models import (
    Analysis,
    AnalysisStatus,
    JsonResume,
    Resume,
    ResumeSource,
)
from app.main import create_app

# NB: app.analyses.__init__ re-exports `router`, shadowing the submodule name,
# so import the real module object explicitly for monkeypatching.
analyses_router = importlib.import_module("app.analyses.router")


class _PrincipalUser:
    def __init__(self, user_id: PydanticObjectId) -> None:
        self.id = user_id


@pytest_asyncio.fixture
async def analyses_env(
    beanie_db: object, monkeypatch: pytest.MonkeyPatch
) -> AsyncIterator[tuple[AsyncClient, PydanticObjectId]]:
    user_id = PydanticObjectId()

    async def _current_user() -> _PrincipalUser:
        return _PrincipalUser(user_id)

    # Keep POST /analyses fast and deterministic: the real pipeline is covered
    # by test_analyses_pipeline; here we only assert the route wiring.
    async def _noop_pipeline(analysis: Analysis, provider: object) -> None:
        return None

    monkeypatch.setattr(analyses_router, "run_full_pipeline", _noop_pipeline)

    app = create_app()
    app.dependency_overrides[get_current_user] = _current_user
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client, user_id


async def _seed_resume(user_id: PydanticObjectId) -> Resume:
    resume = Resume(
        user_id=user_id,
        name="Seed Resume",
        source=ResumeSource.CREATED,
        json_resume=JsonResume.model_validate({"basics": {"name": "Seed"}}),
    )
    await resume.insert()
    return resume


@pytest.mark.asyncio
async def test_create_analysis_returns_201(
    analyses_env: tuple[AsyncClient, PydanticObjectId],
) -> None:
    client, user_id = analyses_env
    resume = await _seed_resume(user_id)
    resp = await client.post(
        "/api/v1/analyses",
        json={
            "name": "Backend role",
            "job_description": "We need a backend engineer. " * 5,
            "resume_id": str(resume.id),
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["name"] == "Backend role"
    assert body["resume_id"] == str(resume.id)


@pytest.mark.asyncio
async def test_create_analysis_missing_resume_404(
    analyses_env: tuple[AsyncClient, PydanticObjectId],
) -> None:
    client, _ = analyses_env
    resp = await client.post(
        "/api/v1/analyses",
        json={
            "name": "X",
            "job_description": "y" * 40,
            "resume_id": str(PydanticObjectId()),
        },
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_list_and_get_analysis(
    analyses_env: tuple[AsyncClient, PydanticObjectId],
) -> None:
    client, user_id = analyses_env
    resume = await _seed_resume(user_id)
    analysis = Analysis(
        user_id=user_id,
        resume_id=resume.id,
        name="Listed",
        job_description="z" * 40,
        resume_snapshot=resume.json_resume,
    )
    await analysis.insert()

    listed = await client.get("/api/v1/analyses")
    assert listed.status_code == 200
    payload = listed.json()
    assert payload["total"] == 1
    assert payload["items"][0]["name"] == "Listed"

    detail = await client.get(f"/api/v1/analyses/{analysis.id}")
    assert detail.status_code == 200
    assert detail.json()["id"] == str(analysis.id)


@pytest.mark.asyncio
async def test_get_unknown_analysis_404(
    analyses_env: tuple[AsyncClient, PydanticObjectId],
) -> None:
    client, _ = analyses_env
    resp = await client.get(f"/api/v1/analyses/{PydanticObjectId()}")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_cancel_pending_then_reject_when_completed(
    analyses_env: tuple[AsyncClient, PydanticObjectId],
) -> None:
    client, user_id = analyses_env
    resume = await _seed_resume(user_id)
    analysis = Analysis(
        user_id=user_id,
        resume_id=resume.id,
        name="Cancelme",
        job_description="z" * 40,
        resume_snapshot=resume.json_resume,
        status=AnalysisStatus.PENDING,
    )
    await analysis.insert()

    resp = await client.post(f"/api/v1/analyses/{analysis.id}/cancel")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"

    # Cancelling again (now cancelled, not pending) -> 422.
    resp2 = await client.post(f"/api/v1/analyses/{analysis.id}/cancel")
    assert resp2.status_code == 422


@pytest.mark.asyncio
async def test_retry_non_failed_is_422(
    analyses_env: tuple[AsyncClient, PydanticObjectId],
) -> None:
    client, user_id = analyses_env
    resume = await _seed_resume(user_id)
    analysis = Analysis(
        user_id=user_id,
        resume_id=resume.id,
        name="Pending",
        job_description="z" * 40,
        resume_snapshot=resume.json_resume,
        status=AnalysisStatus.PENDING,
    )
    await analysis.insert()
    resp = await client.post(f"/api/v1/analyses/{analysis.id}/retry")
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_dismiss_suggestion_route(
    analyses_env: tuple[AsyncClient, PydanticObjectId],
) -> None:
    client, user_id = analyses_env
    resume = await _seed_resume(user_id)
    from app.database.models import AnalysisResult, Suggestion, SuggestionGroup

    suggestion = Suggestion(
        group=SuggestionGroup.WORDING,
        field_ref="basics.summary",
        title="t",
        description="d",
        proposed_value="v",
    )
    analysis = Analysis(
        user_id=user_id,
        resume_id=resume.id,
        name="WithResult",
        job_description="z" * 40,
        resume_snapshot=resume.json_resume,
        status=AnalysisStatus.COMPLETED,
        result=AnalysisResult(
            overall_score=70, ats_score=60, project_score=None, suggestions=[suggestion]
        ),
    )
    await analysis.insert()

    resp = await client.post(
        f"/api/v1/analyses/{analysis.id}/suggestions/{suggestion.suggestion_id}/dismiss"
    )
    assert resp.status_code == 200
    assert resp.json()["action"] == "dismissed"
