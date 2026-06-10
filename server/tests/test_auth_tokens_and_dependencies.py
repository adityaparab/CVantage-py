from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, cast

import pytest
from fastapi import HTTPException

import app.auth.dependencies as deps
import app.auth.tokens as tokens
from app.config import Settings
from app.database.models import UserRole, UserStatus


@dataclass(slots=True)
class _FakeUser:
    role: UserRole = UserRole.CANDIDATE
    status: UserStatus = UserStatus.ACTIVE
    last_active_at: datetime | None = None
    save_calls: int = 0

    async def save(self) -> None:
        self.save_calls += 1


def test_create_and_decode_access_token_roundtrip() -> None:
    settings = Settings(
        environment="test",
        auth_access_token_secret="secret",
        auth_access_token_ttl_seconds=300,
    )

    token = tokens.create_access_token("user-123", settings)
    subject = tokens.decode_access_token(token, settings)

    assert subject == "user-123"


def test_decode_access_token_invalid_signature_returns_none() -> None:
    settings = Settings(environment="test", auth_access_token_secret="secret")

    subject = tokens.decode_access_token("invalid-token", settings)

    assert subject is None


@pytest.mark.asyncio
async def test_get_current_user_requires_auth_header() -> None:
    settings = Settings(environment="test")

    with pytest.raises(HTTPException) as exc_info:
        await deps.get_current_user(settings=settings, authorization=None)

    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_get_current_user_rejects_invalid_token(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = Settings(environment="test")

    async def _none_user(_: str, __: Settings) -> _FakeUser | None:
        return None

    monkeypatch.setattr(deps, "get_user_by_token", _none_user)

    with pytest.raises(HTTPException) as exc_info:
        await deps.get_current_user(settings=settings, authorization="Bearer invalid")

    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_get_current_user_blocks_deactivated(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = Settings(environment="test")

    async def _deactivated(_: str, __: Settings) -> _FakeUser | None:
        return _FakeUser(status=UserStatus.DEACTIVATED)

    monkeypatch.setattr(deps, "get_user_by_token", _deactivated)

    with pytest.raises(HTTPException) as exc_info:
        await deps.get_current_user(settings=settings, authorization="Bearer token")

    assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_require_role_denies_candidate_for_admin_route() -> None:
    guard = deps.require_role(UserRole.ADMIN)

    with pytest.raises(HTTPException) as exc_info:
        await guard(cast(Any, _FakeUser(role=UserRole.CANDIDATE)))

    assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_get_current_user_touches_last_active_at_no_more_than_once_per_5min(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = Settings(environment="test")
    user = _FakeUser(last_active_at=datetime(2026, 1, 1, tzinfo=UTC))

    async def _active(_: str, __: Settings) -> _FakeUser | None:
        return user

    now = datetime(2026, 1, 1, 0, 1, tzinfo=UTC)
    monkeypatch.setattr(deps, "get_user_by_token", _active)
    monkeypatch.setattr(deps, "_utcnow", lambda: now)

    result = await deps.get_current_user(settings=settings, authorization="Bearer token")

    assert result is user
    assert user.save_calls == 0
    assert user.last_active_at == datetime(2026, 1, 1, tzinfo=UTC)

    monkeypatch.setattr(deps, "_utcnow", lambda: datetime(2026, 1, 1, 0, 6, tzinfo=UTC))
    result = await deps.get_current_user(settings=settings, authorization="Bearer token")

    assert result is user
    assert user.save_calls == 1
    assert user.last_active_at == datetime(2026, 1, 1, 0, 6, tzinfo=UTC)
