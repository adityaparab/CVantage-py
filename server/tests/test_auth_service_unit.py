from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, cast

import pytest
from fastapi import HTTPException
from pymongo.errors import DuplicateKeyError

import app.auth.service as service
from app.auth.schemas import LoginRequest, RegisterRequest
from app.config import Settings
from app.database.models import AuthToken, TokenKind, UserStatus


@dataclass(slots=True)
class _FakeUserRecord:
    id: str
    email: str
    full_name: str
    password_hash: str | None
    status: UserStatus = UserStatus.ACTIVE


class _FakeUserModel:
    email = object()
    next_find_one: _FakeUserRecord | None = None
    next_get: _FakeUserRecord | None = None

    def __init__(self, **kwargs: Any) -> None:
        self.id = "user-1"
        self.email = kwargs["email"]
        self.full_name = kwargs["full_name"]
        self.password_hash = kwargs.get("password_hash")
        self.status = kwargs.get("status", UserStatus.ACTIVE)

    async def insert(self) -> None:
        if self.email == "duplicate@example.com":
            raise DuplicateKeyError("dup")

    @classmethod
    async def find_one(cls, _: object) -> _FakeUserRecord | None:
        return cls.next_find_one

    @classmethod
    async def get(cls, _: object) -> _FakeUserRecord | None:
        return cls.next_get


class _FakeAuditLog:
    inserted = 0

    def __init__(self, **_: Any) -> None:
        pass

    async def insert(self) -> None:
        _FakeAuditLog.inserted += 1


@dataclass(slots=True)
class _FakeAuthToken:
    user_id: str
    kind: TokenKind
    token_hash: str
    expires_at: datetime
    consumed_at: datetime | None = None

    async def save(self) -> None:
        return None


@dataclass(slots=True)
class _FakeRequest:
    class _Client:
        host = "127.0.0.1"

    client = _Client()
    headers: dict[str, str] | None = None


@pytest.mark.asyncio
async def test_register_user_rejects_weak_password() -> None:
    with pytest.raises(HTTPException) as exc_info:
        await service.register_user(
            RegisterRequest(
                email="candidate@example.com",
                fullName="Jane Candidate",
                password="weakpass",
            ),
            Settings(environment="test"),
        )

    assert exc_info.value.status_code == 422


@pytest.mark.asyncio
async def test_register_user_duplicate_email_conflict(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(service, "User", _FakeUserModel)
    monkeypatch.setattr(service, "AuditLog", _FakeAuditLog)

    with pytest.raises(HTTPException) as exc_info:
        await service.register_user(
            RegisterRequest(
                email="duplicate@example.com",
                fullName="Jane Candidate",
                password="StrongPass#2026",
            ),
            Settings(environment="test"),
        )

    assert exc_info.value.status_code == 409


@pytest.mark.asyncio
async def test_login_unknown_and_bad_password(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(service, "User", _FakeUserModel)
    _FakeUserModel.next_find_one = None

    with pytest.raises(HTTPException) as unknown_exc:
        await service.login_user(
            LoginRequest(email="missing@example.com", password="StrongPass#2026"),
            Settings(environment="test"),
            cast(Any, _FakeRequest()),
        )
    assert unknown_exc.value.status_code == 401

    _FakeUserModel.next_find_one = _FakeUserRecord(
        id="user-1",
        email="candidate@example.com",
        full_name="Jane Candidate",
        password_hash="hash",
        status=UserStatus.ACTIVE,
    )
    monkeypatch.setattr(service, "verify_password", lambda *_: False)

    with pytest.raises(HTTPException) as wrong_exc:
        await service.login_user(
            LoginRequest(email="candidate@example.com", password="WrongPass#2026"),
            Settings(environment="test"),
            cast(Any, _FakeRequest()),
        )
    assert wrong_exc.value.status_code == 401


@pytest.mark.asyncio
async def test_login_success_returns_access_and_refresh(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(service, "User", _FakeUserModel)
    monkeypatch.setattr(service, "AuditLog", _FakeAuditLog)
    _FakeAuditLog.inserted = 0

    _FakeUserModel.next_find_one = _FakeUserRecord(
        id="user-1",
        email="candidate@example.com",
        full_name="Jane Candidate",
        password_hash="hash",
        status=UserStatus.ACTIVE,
    )
    monkeypatch.setattr(service, "verify_password", lambda *_: True)
    monkeypatch.setattr(service, "create_access_token", lambda *_: "access-token")

    async def _issue_refresh(*_: object) -> str:
        return "refresh-token"

    monkeypatch.setattr(service, "_issue_refresh_token", _issue_refresh)

    access_token, refresh_token = await service.login_user(
        LoginRequest(email="candidate@example.com", password="StrongPass#2026"),
        Settings(environment="test"),
        cast(Any, _FakeRequest()),
    )

    assert access_token == "access-token"
    assert refresh_token == "refresh-token"
    assert _FakeAuditLog.inserted == 1


@pytest.mark.asyncio
async def test_refresh_rotates_token(monkeypatch: pytest.MonkeyPatch) -> None:
    token = _FakeAuthToken(
        user_id="user-1",
        kind=TokenKind.REFRESH,
        token_hash="hash",
        expires_at=datetime.now(UTC) + timedelta(days=1),
    )

    class _FakeAuthTokenModel:
        @staticmethod
        async def find_one(*_: object) -> _FakeAuthToken:
            return token

    monkeypatch.setattr(service, "AuthToken", _FakeAuthTokenModel)

    class _FakeUserGet:
        @staticmethod
        async def get(*_: object) -> _FakeUserRecord:
            return _FakeUserRecord("user-1", "a@b.com", "A", "h")

    monkeypatch.setattr(
        service,
        "User",
        _FakeUserGet,
    )
    monkeypatch.setattr(service, "create_access_token", lambda *_: "access-rotated")

    async def _issue_refresh(*_: object) -> str:
        return "refresh-rotated"

    monkeypatch.setattr(service, "_issue_refresh_token", _issue_refresh)

    access_token, refresh_token = await service.refresh_user_session(
        "refresh-in",
        Settings(environment="test"),
        cast(Any, _FakeRequest()),
    )

    assert access_token == "access-rotated"
    assert refresh_token == "refresh-rotated"
    assert token.consumed_at is not None


@pytest.mark.asyncio
async def test_refresh_reuse_revokes_family(monkeypatch: pytest.MonkeyPatch) -> None:
    token = _FakeAuthToken(
        user_id="user-1",
        kind=TokenKind.REFRESH,
        token_hash="hash",
        expires_at=datetime.now(UTC) + timedelta(days=1),
        consumed_at=datetime.now(UTC),
    )

    class _FakeAuthTokenModel:
        @staticmethod
        async def find_one(*_: object) -> _FakeAuthToken:
            return token

    monkeypatch.setattr(service, "AuthToken", _FakeAuthTokenModel)
    monkeypatch.setattr(service, "AuditLog", _FakeAuditLog)

    called = {"revoked": False}

    async def _revoke(_: object) -> None:
        called["revoked"] = True

    monkeypatch.setattr(service, "_revoke_user_refresh_family", _revoke)

    with pytest.raises(HTTPException) as exc_info:
        await service.refresh_user_session(
            "reused",
            Settings(environment="test"),
            cast(Any, _FakeRequest()),
        )

    assert exc_info.value.status_code == 401
    assert called["revoked"] is True


@pytest.mark.asyncio
async def test_logout_revokes_family_when_refresh_present(monkeypatch: pytest.MonkeyPatch) -> None:
    token = _FakeAuthToken(
        user_id="user-1",
        kind=TokenKind.REFRESH,
        token_hash="hash",
        expires_at=datetime.now(UTC) + timedelta(days=1),
    )

    class _FakeAuthTokenModel:
        @staticmethod
        async def find_one(*_: object) -> _FakeAuthToken:
            return token

    monkeypatch.setattr(service, "AuthToken", _FakeAuthTokenModel)
    monkeypatch.setattr(service, "AuditLog", _FakeAuditLog)

    called = {"revoked": False}

    async def _revoke(_: object) -> None:
        called["revoked"] = True

    monkeypatch.setattr(service, "_revoke_user_refresh_family", _revoke)

    await service.logout_user_session("refresh-token", cast(Any, _FakeRequest()))

    assert called["revoked"] is True


def test_refresh_token_ttl_index_declared() -> None:
    ttl_indexes = [
        index for index in AuthToken.Settings.indexes if index.document.get("name") == "ttl"
    ]
    assert ttl_indexes
    assert ttl_indexes[0].document.get("expireAfterSeconds") == 0
