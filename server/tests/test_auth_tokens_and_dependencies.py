from __future__ import annotations

from dataclasses import dataclass

import pytest
from fastapi import HTTPException

import app.auth.dependencies as deps
import app.auth.tokens as tokens
from app.config import Settings
from app.database.models import UserStatus


@dataclass(slots=True)
class _FakeUser:
    status: UserStatus = UserStatus.ACTIVE


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
