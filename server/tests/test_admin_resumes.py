"""Privacy-bounded admin resume administration tests (issue #61).

Proves: admin resume views are metadata-only (no content), the delete cascade
soft-deletes analyses and clears their notifications, the cascade is idempotent,
and candidates can no longer see cascade-deleted analyses.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from beanie import PydanticObjectId
from httpx import ASGITransport, AsyncClient

from app.admin.schemas import AdminResumeListItem
from app.auth.dependencies import get_current_user
from app.auth.passwords import hash_password
from app.database.models import (
    Analysis,
    AnalysisStatus,
    AuditAction,
    AuditLog,
    JsonResume,
    Notification,
    NotificationState,
    NotificationType,
    OriginalFile,
    Resume,
    ResumeSource,
    User,
    UserRole,
)
from app.main import create_app


async def _make_user(*, email: str, role: UserRole = UserRole.CANDIDATE) -> User:
    user = User(email=email, full_name="U", password_hash=hash_password("OldPassw0rd!"), role=role)
    await user.insert()
    return user


def _client_for(user: User) -> AsyncClient:
    async def _current_user() -> User:
        return user

    app = create_app()
    app.dependency_overrides[get_current_user] = _current_user
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def _seed_resume_with_analysis(
    owner: PydanticObjectId | None,
) -> tuple[Resume, Analysis, Notification]:
    assert owner is not None
    resume = Resume(
        user_id=owner,
        name="Owner Resume",
        source=ResumeSource.UPLOADED,
        json_resume=JsonResume.model_validate({"basics": {"name": "Owner"}}),
        original_text="SECRET RESUME TEXT",
        original_file=OriginalFile(
            file_name="resume.pdf",
            mime_type="application/pdf",
            size_bytes=1024,
            storage_key="uploads/resume.pdf",
            sha256=None,
        ),
    )
    await resume.insert()
    analysis = Analysis(
        user_id=owner,
        resume_id=resume.id,
        name="A",
        job_description="x" * 40,
        resume_snapshot=resume.json_resume,
        status=AnalysisStatus.PENDING,
    )
    await analysis.insert()
    notif = Notification(
        user_id=owner,
        analysis_id=analysis.id,
        type=NotificationType.ANALYSIS_COMPLETED,
        title="done",
    )
    await notif.insert()
    return resume, analysis, notif


@pytest_asyncio.fixture
async def admin_client(beanie_db: object) -> AsyncIterator[tuple[AsyncClient, User]]:
    admin = await _make_user(email="admin@cvantage.io", role=UserRole.ADMIN)
    async with _client_for(admin) as client:
        yield client, admin


# ---------------------------------------------------------------------------
# Privacy: metadata only
# ---------------------------------------------------------------------------


def test_resume_dto_has_no_content_fields() -> None:
    fields = set(AdminResumeListItem.model_fields)
    assert "json_resume" not in fields
    assert "original_text" not in fields


@pytest.mark.asyncio
async def test_list_user_resumes_metadata_only(
    admin_client: tuple[AsyncClient, User],
) -> None:
    client, _ = admin_client
    owner = await _make_user(email="owner@corp.io")
    await _seed_resume_with_analysis(owner.id)

    resp = await client.get(f"/api/v1/admin/users/{owner.id}/resumes")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    item = body["items"][0]
    assert item["name"] == "Owner Resume"
    # No content leaks anywhere in the payload.
    assert "jsonResume" not in item and "json_resume" not in item
    assert "originalText" not in item and "original_text" not in item
    assert "SECRET RESUME TEXT" not in resp.text


@pytest.mark.asyncio
async def test_list_resumes_unknown_user_404(
    admin_client: tuple[AsyncClient, User],
) -> None:
    client, _ = admin_client
    resp = await client.get(f"/api/v1/admin/users/{PydanticObjectId()}/resumes")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# RBAC
# ---------------------------------------------------------------------------


@pytest.mark.usefixtures("beanie_db")
@pytest.mark.asyncio
async def test_candidate_forbidden_on_resume_admin() -> None:
    candidate = await _make_user(email="cand@corp.io")
    owner = await _make_user(email="owner2@corp.io")
    resume, _, _ = await _seed_resume_with_analysis(owner.id)
    async with _client_for(candidate) as client:
        r1 = await client.get(f"/api/v1/admin/users/{owner.id}/resumes")
        r2 = await client.delete(f"/api/v1/admin/resumes/{resume.id}")
    assert r1.status_code == 403
    assert r2.status_code == 403


# ---------------------------------------------------------------------------
# Cascade delete
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_cascades_and_clears_notifications(
    admin_client: tuple[AsyncClient, User],
) -> None:
    client, _ = admin_client
    owner = await _make_user(email="cascade@corp.io")
    resume, analysis, notif = await _seed_resume_with_analysis(owner.id)

    resp = await client.delete(f"/api/v1/admin/resumes/{resume.id}")
    assert resp.status_code == 200

    reloaded_resume = await Resume.get(resume.id)
    assert reloaded_resume is not None and reloaded_resume.deleted_at is not None
    reloaded_analysis = await Analysis.get(analysis.id)
    assert reloaded_analysis is not None and reloaded_analysis.deleted_at is not None
    reloaded_notif = await Notification.get(notif.id)
    assert reloaded_notif is not None
    assert reloaded_notif.state == NotificationState.CLEARED

    audit = await AuditLog.find_one({"action": AuditAction.ADMIN_RESUME_DELETE.value})
    assert audit is not None
    assert audit.target_type == "resume"


@pytest.mark.asyncio
async def test_delete_unknown_resume_404(admin_client: tuple[AsyncClient, User]) -> None:
    client, _ = admin_client
    resp = await client.delete(f"/api/v1/admin/resumes/{PydanticObjectId()}")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_is_idempotent(admin_client: tuple[AsyncClient, User]) -> None:
    client, _ = admin_client
    owner = await _make_user(email="idem@corp.io")
    resume, _, _ = await _seed_resume_with_analysis(owner.id)

    first = await client.delete(f"/api/v1/admin/resumes/{resume.id}")
    assert first.status_code == 200
    second = await client.delete(f"/api/v1/admin/resumes/{resume.id}")
    assert second.status_code == 200  # no-op, not an error

    # Exactly one audit entry — the re-run did not re-audit.
    count = await AuditLog.find({"action": AuditAction.ADMIN_RESUME_DELETE.value}).count()
    assert count == 1


@pytest.mark.asyncio
async def test_deleted_analyses_hidden_from_candidate(
    admin_client: tuple[AsyncClient, User],
) -> None:
    client, _ = admin_client
    owner = await _make_user(email="hidden@corp.io")
    resume, _, _ = await _seed_resume_with_analysis(owner.id)
    await client.delete(f"/api/v1/admin/resumes/{resume.id}")

    # The owning candidate no longer sees the cascade-deleted analysis.
    async with _client_for(owner) as owner_client:
        listed = await owner_client.get("/api/v1/analyses")
    assert listed.status_code == 200
    assert listed.json()["total"] == 0
