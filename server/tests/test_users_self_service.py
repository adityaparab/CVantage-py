from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Annotated

import pytest
import pytest_asyncio
from fastapi import Header, HTTPException
from httpx import ASGITransport, AsyncClient

import app.users.service as users_service
from app.auth.dependencies import get_current_user
from app.auth.passwords import hash_password, verify_password
from app.database.models import UserRole, UserStatus
from app.main import create_app


@dataclass(slots=True)
class _FakeUser:
    id: str
    email: str
    full_name: str
    password_hash: str | None
    role: UserRole = UserRole.CANDIDATE
    status: UserStatus = UserStatus.ACTIVE
    avatar_url: str | None = None
    email_verified: bool = False
    resume_count: int = 0
    analysis_count: int = 0
    save_calls: int = 0

    async def save(self) -> None:
        self.save_calls += 1


@pytest_asyncio.fixture
async def users_client(
    monkeypatch: pytest.MonkeyPatch,
) -> AsyncIterator[tuple[AsyncClient, _FakeUser, dict[str, bool]]]:
    user = _FakeUser(
        id="user-1",
        email="candidate@example.com",
        full_name="Jane Candidate",
        password_hash=hash_password("StrongPass#2026"),
        avatar_url="https://cdn.example.com/avatar.png",
        email_verified=True,
        resume_count=2,
        analysis_count=3,
    )

    async def _current_user(
        authorization: Annotated[str | None, Header()] = None,
    ) -> _FakeUser:
        if authorization != "Bearer token":
            raise HTTPException(status_code=401, detail={"message": "Authentication required"})
        return user

    revoked = {"called": False}

    async def _revoke(_: object) -> None:
        revoked["called"] = True

    monkeypatch.setattr(users_service, "_revoke_user_refresh_family", _revoke)

    app = create_app()
    app.dependency_overrides[get_current_user] = _current_user

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client, user, revoked


@pytest.mark.asyncio
async def test_get_users_me_is_sanitized_with_counters(
    users_client: tuple[AsyncClient, _FakeUser, dict[str, bool]],
) -> None:
    client, _, _ = users_client
    response = await client.get(
        "/api/v1/users/me",
        headers={"Authorization": "Bearer token"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["email"] == "candidate@example.com"
    assert body["resumeCount"] == 2
    assert body["analysisCount"] == 3
    assert "passwordHash" not in body
    assert "oauthIdentities" not in body


@pytest.mark.asyncio
async def test_patch_users_me_updates_allowed_fields(
    users_client: tuple[AsyncClient, _FakeUser, dict[str, bool]],
) -> None:
    client, _, _ = users_client
    response = await client.patch(
        "/api/v1/users/me",
        headers={"Authorization": "Bearer token"},
        json={
            "fullName": "Updated Candidate",
            "avatarUrl": "https://cdn.example.com/new.png",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["fullName"] == "Updated Candidate"
    assert body["avatarUrl"] == "https://cdn.example.com/new.png"


@pytest.mark.asyncio
async def test_change_password_wrong_current_returns_403(
    users_client: tuple[AsyncClient, _FakeUser, dict[str, bool]],
) -> None:
    client, _, _ = users_client
    response = await client.post(
        "/api/v1/users/me/password",
        headers={"Authorization": "Bearer token"},
        json={
            "currentPassword": "WrongPass#2026",
            "newPassword": "NewStrongPass#2026",
        },
    )

    assert response.status_code == 403
    assert response.json()["message"] == "Current password is incorrect"


@pytest.mark.asyncio
async def test_change_password_success_updates_hash_and_revokes(
    users_client: tuple[AsyncClient, _FakeUser, dict[str, bool]],
) -> None:
    client, user, revoked = users_client
    response = await client.post(
        "/api/v1/users/me/password",
        headers={"Authorization": "Bearer token"},
        json={
            "currentPassword": "StrongPass#2026",
            "newPassword": "NewStrongPass#2026",
        },
    )

    assert response.status_code == 200
    assert user.password_hash is not None
    assert verify_password("NewStrongPass#2026", user.password_hash)
    assert revoked["called"] is True
