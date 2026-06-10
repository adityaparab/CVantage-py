"""Realtime test suite — notifications + SSE event streams (issue #58).

Covers the notifications service/router lifecycle and the analysis SSE
generator (snapshot, status-change, terminal, and not-found paths).
"""

from __future__ import annotations

import importlib
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from beanie import PydanticObjectId
from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient

from app.auth.dependencies import get_current_user
from app.database.models import (
    Analysis,
    AnalysisStatus,
    JsonResume,
    NotificationType,
    Resume,
    ResumeSource,
)
from app.main import create_app
from app.notifications import service as notif_service

events = importlib.import_module("app.analyses.events")


class _PrincipalUser:
    def __init__(self, user_id: PydanticObjectId) -> None:
        self.id = user_id


async def _seed_analysis(user_id: PydanticObjectId, status: AnalysisStatus) -> Analysis:
    resume = Resume(
        user_id=user_id,
        name="R",
        source=ResumeSource.CREATED,
        json_resume=JsonResume.model_validate({"basics": {"name": "N"}}),
    )
    await resume.insert()
    analysis = Analysis(
        user_id=user_id,
        resume_id=resume.id,
        name="A",
        job_description="x" * 40,
        resume_snapshot=resume.json_resume,
        status=status,
    )
    await analysis.insert()
    return analysis


# ---------------------------------------------------------------------------
# Notifications service
# ---------------------------------------------------------------------------


@pytest.mark.usefixtures("beanie_db")
class TestNotificationsService:
    @pytest.mark.asyncio
    async def test_single_active_per_analysis_replaced_in_place(self) -> None:
        user_id = PydanticObjectId()
        analysis_id = PydanticObjectId()
        await notif_service.create_analysis_start_notification(user_id, analysis_id, "A")
        await notif_service.create_analysis_complete_notification(user_id, analysis_id, "A")

        active = await notif_service.list_active_notifications(user_id)
        assert len(active) == 1
        assert active[0]["type"] == NotificationType.ANALYSIS_COMPLETED.value

    @pytest.mark.asyncio
    async def test_clear_missing_notification_404(self) -> None:
        with pytest.raises(HTTPException) as exc:
            await notif_service.clear_notification(PydanticObjectId(), PydanticObjectId())
        assert exc.value.status_code == 404

    @pytest.mark.asyncio
    async def test_auto_clear_for_analysis(self) -> None:
        user_id = PydanticObjectId()
        analysis_id = PydanticObjectId()
        await notif_service.create_analysis_start_notification(user_id, analysis_id, "A")
        await notif_service.auto_clear_for_analysis(analysis_id, user_id)
        active = await notif_service.list_active_notifications(user_id)
        assert active == []


# ---------------------------------------------------------------------------
# Notifications router
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def notif_client(
    beanie_db: object,
) -> AsyncIterator[tuple[AsyncClient, PydanticObjectId]]:
    user_id = PydanticObjectId()

    async def _current_user() -> _PrincipalUser:
        return _PrincipalUser(user_id)

    app = create_app()
    app.dependency_overrides[get_current_user] = _current_user
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client, user_id


@pytest.mark.asyncio
async def test_list_and_clear_notifications_endpoints(
    notif_client: tuple[AsyncClient, PydanticObjectId],
) -> None:
    client, user_id = notif_client
    analysis_id = PydanticObjectId()
    notif = await notif_service.create_analysis_start_notification(user_id, analysis_id, "A")

    listed = await client.get("/api/v1/notifications")
    assert listed.status_code == 200
    assert listed.json()["total"] == 1

    cleared = await client.post(f"/api/v1/notifications/{notif.id}/clear")
    assert cleared.status_code == 200

    after = await client.get("/api/v1/notifications")
    assert after.json()["total"] == 0


@pytest.mark.asyncio
async def test_clear_unknown_notification_returns_404(
    notif_client: tuple[AsyncClient, PydanticObjectId],
) -> None:
    client, _ = notif_client
    resp = await client.post(f"/api/v1/notifications/{PydanticObjectId()}/clear")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# SSE event streams
# ---------------------------------------------------------------------------


@pytest.mark.usefixtures("beanie_db")
class TestSseEvents:
    def setup_method(self) -> None:
        events._active_connections.clear()

    @pytest.mark.asyncio
    async def test_stream_unknown_analysis_404(self) -> None:
        with pytest.raises(HTTPException) as exc:
            await events.stream_analysis_events(PydanticObjectId(), PydanticObjectId())
        assert exc.value.status_code == 404

    @pytest.mark.asyncio
    async def test_stream_connection_cap_429(self) -> None:
        user_id = PydanticObjectId()
        analysis = await _seed_analysis(user_id, AnalysisStatus.PENDING)
        events._active_connections[str(user_id)] = events.MAX_CONNECTIONS_PER_USER
        with pytest.raises(HTTPException) as exc:
            await events.stream_analysis_events(analysis.id, user_id)
        assert exc.value.status_code == 429

    @pytest.mark.asyncio
    async def test_stream_returns_event_source_response(self) -> None:
        user_id = PydanticObjectId()
        analysis = await _seed_analysis(user_id, AnalysisStatus.PENDING)
        resp = await events.stream_analysis_events(analysis.id, user_id)
        assert resp.status_code == 200
        assert events._active_connections[str(user_id)] == 1

    @pytest.mark.asyncio
    async def test_generator_emits_snapshot(self) -> None:
        user_id = PydanticObjectId()
        analysis = await _seed_analysis(user_id, AnalysisStatus.PENDING)
        gen = events._analysis_event_generator(analysis.id, str(user_id))
        first = await gen.__anext__()
        assert first["event"] == "snapshot"
        await gen.aclose()

    @pytest.mark.asyncio
    async def test_generator_emits_status_change_then_done(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        async def _fast_sleep(_seconds: float) -> None:
            return None

        monkeypatch.setattr(events.asyncio, "sleep", _fast_sleep)

        user_id = PydanticObjectId()
        analysis = await _seed_analysis(user_id, AnalysisStatus.PENDING)
        gen = events._analysis_event_generator(analysis.id, str(user_id))
        await gen.__anext__()  # snapshot

        # Flip to a terminal status; next polls should report the change + done.
        current = await Analysis.get(analysis.id)
        assert current is not None
        current.status = AnalysisStatus.FAILED
        await current.save()

        change = await gen.__anext__()
        assert change["event"] == "status_change"
        done = await gen.__anext__()
        assert done["event"] == "done"
        await gen.aclose()

    @pytest.mark.asyncio
    async def test_generator_handles_deleted_analysis(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        async def _fast_sleep(_seconds: float) -> None:
            return None

        monkeypatch.setattr(events.asyncio, "sleep", _fast_sleep)

        user_id = PydanticObjectId()
        analysis = await _seed_analysis(user_id, AnalysisStatus.PENDING)
        gen = events._analysis_event_generator(analysis.id, str(user_id))
        await gen.__anext__()  # snapshot

        fetched = await Analysis.get(analysis.id)
        assert fetched is not None
        await fetched.delete()

        evt = await gen.__anext__()
        assert evt["event"] == "error"
        await gen.aclose()
