"""Tests for Resume CRUD endpoints (issue #41).

Uses monkeypatching to replace the service-layer functions with
in-memory state so no MongoDB is needed.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Annotated, Any

import pytest
import pytest_asyncio
from fastapi import Header, HTTPException
from httpx import ASGITransport, AsyncClient

import app.resumes.service as resumes_service
from app.auth.dependencies import get_current_user
from app.database.models import UserRole, UserStatus
from app.main import create_app
from app.resumes.schemas import resume_to_clean_dict


def _utcnow() -> datetime:
    return datetime.now(UTC)


@dataclass(slots=True)
class _FakeResume:
    id: str  # valid 24-char hex string (PydanticObjectId format)
    user_id: str
    name: str
    source: str
    json_resume: dict[str, Any]
    analysis_status: str = "unanalyzed"
    original_text: str | None = None
    last_analyzed_at: datetime | None = None
    analysis_count: int = 0
    created_at: datetime = field(default_factory=_utcnow)
    updated_at: datetime = field(default_factory=_utcnow)
    deleted_at: datetime | None = None
    revision_id: int = 0


@dataclass(slots=True)
class _FakeUser:
    id: str
    email: str
    full_name: str
    role: UserRole = UserRole.CANDIDATE
    status: UserStatus = UserStatus.ACTIVE
    avatar_url: str | None = None
    email_verified: bool = False
    resume_count: int = 0
    analysis_count: int = 0


def _resume_to_response(r: _FakeResume) -> dict[str, Any]:
    return {
        "id": r.id,
        "name": r.name,
        "source": r.source,
        "json_resume": r.json_resume,
        "analysis_status": r.analysis_status,
        "original_text": r.original_text,
        "last_analyzed_at": r.last_analyzed_at.isoformat() if r.last_analyzed_at else None,
        "analysis_count": r.analysis_count,
        "created_at": r.created_at.isoformat(),
        "updated_at": r.updated_at.isoformat(),
    }


def _resume_to_list_item(r: _FakeResume) -> dict[str, Any]:
    return {
        "id": r.id,
        "name": r.name,
        "source": r.source,
        "analysis_status": r.analysis_status,
        "last_analyzed_at": r.last_analyzed_at.isoformat() if r.last_analyzed_at else None,
        "analysis_count": r.analysis_count,
        "created_at": r.created_at.isoformat(),
    }


@pytest_asyncio.fixture
async def resumes_client(monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[AsyncClient]:
    _USER1_ID = "665c3ef2c9d8f76b6e4f4f01"
    _USER2_ID = "665c3ef2c9d8f76b6e4f4f02"
    user = _FakeUser(id=_USER1_ID, email="candidate@example.com", full_name="Jane Candidate")
    other_user = _FakeUser(id=_USER2_ID, email="other@example.com", full_name="Other User")

    resumes: dict[str, _FakeResume] = {}
    resume_counter = 0

    async def _create(user_id: object, payload: object) -> dict[str, Any]:
        nonlocal resume_counter
        uid = str(user_id)
        from app.resumes.schemas import CreateResumeRequest

        p = CreateResumeRequest.model_validate(payload)
        for r in resumes.values():
            if r.user_id == uid and r.deleted_at is None and r.name == p.name.strip():
                raise HTTPException(
                    409, detail={"message": "A resume with this name already exists"}
                )

        resume_counter += 1
        resume_id = f"665c3ef2c9d8f76b6e4f4f{resume_counter:02d}"
        cleaned = resume_to_clean_dict(p.json_resume)
        resume = _FakeResume(
            id=resume_id, user_id=uid, name=p.name.strip(), source="created", json_resume=cleaned
        )
        resumes[resume_id] = resume
        return _resume_to_response(resume)

    async def _list(
        user_id: object,
        *,
        skip: int = 0,
        limit: int = 20,
        sort_field: str = "created_at",
        sort_desc: bool = True,
    ) -> dict[str, Any]:
        uid = str(user_id)
        items = sorted(
            [r for r in resumes.values() if r.user_id == uid and r.deleted_at is None],
            key=lambda r: getattr(r, sort_field, r.created_at),
            reverse=sort_desc,
        )
        paginated = items[skip : skip + limit]
        return {
            "items": [_resume_to_list_item(r) for r in paginated],
            "total": len(items),
            "skip": skip,
            "limit": limit,
        }

    async def _get(user_id: object, resume_id: object) -> dict[str, Any]:
        uid, rid = str(user_id), str(resume_id)
        r = resumes.get(rid)
        if r is None or r.user_id != uid or r.deleted_at is not None:
            raise HTTPException(404, detail={"message": "Resume not found"})
        return _resume_to_response(r)

    async def _update(user_id: object, resume_id: object, payload: object) -> dict[str, Any]:
        uid, rid = str(user_id), str(resume_id)
        from app.resumes.schemas import UpdateResumeRequest

        p = UpdateResumeRequest.model_validate(payload)
        r = resumes.get(rid)
        if r is None or r.user_id != uid or r.deleted_at is not None:
            raise HTTPException(404, detail={"message": "Resume not found"})

        if p.name is not None:
            for other in resumes.values():
                if (
                    other.id != rid
                    and other.user_id == uid
                    and other.deleted_at is None
                    and other.name == p.name.strip()
                ):
                    raise HTTPException(
                        409, detail={"message": "A resume with this name already exists"}
                    )
            r.name = p.name.strip()

        if p.json_resume is not None:
            r.json_resume = resume_to_clean_dict(p.json_resume)

        r.revision_id += 1
        r.updated_at = _utcnow()
        return _resume_to_response(r)

    async def _delete(user_id: object, resume_id: object, *, deleted_by: str | None = None) -> None:
        uid, rid = str(user_id), str(resume_id)
        r = resumes.get(rid)
        if r is None or r.user_id != uid or r.deleted_at is not None:
            raise HTTPException(404, detail={"message": "Resume not found"})
        r.deleted_at = _utcnow()

    # Patch service module so the router (which does `import ... as service`) sees mocks
    monkeypatch.setattr(resumes_service, "create_resume", _create)
    monkeypatch.setattr(resumes_service, "list_resumes", _list)
    monkeypatch.setattr(resumes_service, "get_resume", _get)
    monkeypatch.setattr(resumes_service, "update_resume", _update)
    monkeypatch.setattr(resumes_service, "delete_resume", _delete)

    async def _current_user(authorization: Annotated[str | None, Header()] = None) -> _FakeUser:
        if authorization == "Bearer other-token":
            return other_user
        if authorization == "Bearer token":
            return user
        raise HTTPException(401, detail={"message": "Authentication required"})

    app = create_app()
    app.dependency_overrides[get_current_user] = _current_user

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client


# ============================================================================
# Tests
# ============================================================================


class TestCreateResume:
    async def test_success(self, resumes_client: AsyncClient) -> None:
        resp = await resumes_client.post(
            "/api/v1/resumes",
            headers={"Authorization": "Bearer token"},
            json={"name": "My Resume", "json_resume": {"basics": {"name": "Jane Doe"}}},
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["name"] == "My Resume"
        assert body["source"] == "created"
        assert body["analysis_status"] == "unanalyzed"

    async def test_401_without_auth(self, resumes_client: AsyncClient) -> None:
        resp = await resumes_client.post(
            "/api/v1/resumes",
            json={"name": "X", "json_resume": {}},
        )
        assert resp.status_code == 401

    async def test_409_duplicate_name(self, resumes_client: AsyncClient) -> None:
        await resumes_client.post(
            "/api/v1/resumes",
            headers={"Authorization": "Bearer token"},
            json={"name": "Unique", "json_resume": {"basics": {"name": "J"}}},
        )
        resp = await resumes_client.post(
            "/api/v1/resumes",
            headers={"Authorization": "Bearer token"},
            json={"name": "Unique", "json_resume": {"basics": {"name": "J"}}},
        )
        assert resp.status_code == 409

    async def test_placeholder_pruning(self, resumes_client: AsyncClient) -> None:
        resp = await resumes_client.post(
            "/api/v1/resumes",
            headers={"Authorization": "Bearer token"},
            json={
                "name": "Pruned",
                "json_resume": {
                    "basics": {"name": "Jane", "email": "", "label": None},
                    "skills": [],
                    "work": [{"name": "Co", "position": "", "highlights": []}],
                },
            },
        )
        assert resp.status_code == 201
        jr = resp.json()["json_resume"]
        assert jr["basics"]["name"] == "Jane"
        # Empty strings and None values are pruned during clean_dict
        assert jr["basics"].get("email") is None or "email" not in jr["basics"]
        assert jr["basics"].get("label") is None or "label" not in jr["basics"]
        # Empty lists are pruned
        assert "skills" not in jr or jr.get("skills") in (None, [])


class TestListResumes:
    async def test_empty(self, resumes_client: AsyncClient) -> None:
        resp = await resumes_client.get(
            "/api/v1/resumes", headers={"Authorization": "Bearer token"}
        )
        assert resp.status_code == 200
        assert resp.json()["items"] == []
        assert resp.json()["total"] == 0

    async def test_pagination(self, resumes_client: AsyncClient) -> None:
        for i in range(3):
            await resumes_client.post(
                "/api/v1/resumes",
                headers={"Authorization": "Bearer token"},
                json={"name": f"R{i + 1}", "json_resume": {}},
            )
        resp = await resumes_client.get(
            "/api/v1/resumes",
            headers={"Authorization": "Bearer token"},
            params={"skip": 0, "limit": 2},
        )
        assert resp.status_code == 200
        assert len(resp.json()["items"]) == 2
        assert resp.json()["total"] == 3

    async def test_owns_only(self, resumes_client: AsyncClient) -> None:
        await resumes_client.post(
            "/api/v1/resumes",
            headers={"Authorization": "Bearer token"},
            json={"name": "Mine", "json_resume": {}},
        )
        resp = await resumes_client.get(
            "/api/v1/resumes", headers={"Authorization": "Bearer token"}
        )
        assert resp.json()["total"] == 1


class TestGetResume:
    async def test_by_id(self, resumes_client: AsyncClient) -> None:
        created = await resumes_client.post(
            "/api/v1/resumes",
            headers={"Authorization": "Bearer token"},
            json={"name": "My", "json_resume": {"basics": {"name": "J"}}},
        )
        rid = created.json()["id"]
        resp = await resumes_client.get(
            f"/api/v1/resumes/{rid}", headers={"Authorization": "Bearer token"}
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "My"

    async def test_404_foreign_owner(self, resumes_client: AsyncClient) -> None:
        created = await resumes_client.post(
            "/api/v1/resumes",
            headers={"Authorization": "Bearer token"},
            json={"name": "Mine", "json_resume": {}},
        )
        rid = created.json()["id"]
        resp = await resumes_client.get(
            f"/api/v1/resumes/{rid}", headers={"Authorization": "Bearer other-token"}
        )
        assert resp.status_code == 404

    async def test_404_not_found(self, resumes_client: AsyncClient) -> None:
        resp = await resumes_client.get(
            "/api/v1/resumes/000000000000000000000000", headers={"Authorization": "Bearer token"}
        )
        assert resp.status_code == 404


class TestUpdateResume:
    async def test_name(self, resumes_client: AsyncClient) -> None:
        created = await resumes_client.post(
            "/api/v1/resumes",
            headers={"Authorization": "Bearer token"},
            json={"name": "Old", "json_resume": {}},
        )
        rid = created.json()["id"]
        resp = await resumes_client.patch(
            f"/api/v1/resumes/{rid}",
            headers={"Authorization": "Bearer token"},
            json={"name": "New"},
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "New"

    async def test_409_name_conflict(self, resumes_client: AsyncClient) -> None:
        await resumes_client.post(
            "/api/v1/resumes",
            headers={"Authorization": "Bearer token"},
            json={"name": "Existing", "json_resume": {}},
        )
        created = await resumes_client.post(
            "/api/v1/resumes",
            headers={"Authorization": "Bearer token"},
            json={"name": "Orig", "json_resume": {}},
        )
        rid = created.json()["id"]
        resp = await resumes_client.patch(
            f"/api/v1/resumes/{rid}",
            headers={"Authorization": "Bearer token"},
            json={"name": "Existing"},
        )
        assert resp.status_code == 409

    async def test_404_foreign(self, resumes_client: AsyncClient) -> None:
        created = await resumes_client.post(
            "/api/v1/resumes",
            headers={"Authorization": "Bearer token"},
            json={"name": "Mine", "json_resume": {}},
        )
        rid = created.json()["id"]
        resp = await resumes_client.patch(
            f"/api/v1/resumes/{rid}",
            headers={"Authorization": "Bearer other-token"},
            json={"name": "Hacked"},
        )
        assert resp.status_code == 404


class TestDeleteResume:
    async def test_soft_delete(self, resumes_client: AsyncClient) -> None:
        created = await resumes_client.post(
            "/api/v1/resumes",
            headers={"Authorization": "Bearer token"},
            json={"name": "ToDel", "json_resume": {}},
        )
        rid = created.json()["id"]

        del_resp = await resumes_client.delete(
            f"/api/v1/resumes/{rid}", headers={"Authorization": "Bearer token"}
        )
        assert del_resp.status_code == 200
        assert del_resp.json()["status"] == "ok"

        # Excluded from list
        list_resp = await resumes_client.get(
            "/api/v1/resumes", headers={"Authorization": "Bearer token"}
        )
        assert list_resp.json()["total"] == 0

        # Direct access returns 404
        get_resp = await resumes_client.get(
            f"/api/v1/resumes/{rid}", headers={"Authorization": "Bearer token"}
        )
        assert get_resp.status_code == 404

    async def test_404_foreign(self, resumes_client: AsyncClient) -> None:
        created = await resumes_client.post(
            "/api/v1/resumes",
            headers={"Authorization": "Bearer token"},
            json={"name": "Mine", "json_resume": {}},
        )
        rid = created.json()["id"]
        resp = await resumes_client.delete(
            f"/api/v1/resumes/{rid}", headers={"Authorization": "Bearer other-token"}
        )
        assert resp.status_code == 404

    async def test_401_without_auth(self, resumes_client: AsyncClient) -> None:
        resp = await resumes_client.delete("/api/v1/resumes/000000000000000000000000")
        assert resp.status_code == 401
