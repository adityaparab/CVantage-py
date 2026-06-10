from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest
from fastapi import HTTPException
from pymongo.errors import DuplicateKeyError

import app.auth.service as service
from app.auth.schemas import LoginRequest, RegisterRequest
from app.config import Settings
from app.database.models import UserStatus


@dataclass(slots=True)
class _FakeUserRecord:
    id: str
    email: str
    full_name: str
    password_hash: str | None
    status: UserStatus = UserStatus.ACTIVE

    async def insert(self) -> None:
        if self.email == "duplicate@example.com":
            raise DuplicateKeyError("dup")


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
    async def get(cls, _: str) -> _FakeUserRecord | None:
        return cls.next_get


class _FakeAuditLog:
    inserted = 0

    def __init__(self, **_: Any) -> None:
        pass

    async def insert(self) -> None:
        _FakeAuditLog.inserted += 1


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
        )
    assert wrong_exc.value.status_code == 401


@pytest.mark.asyncio
async def test_login_deactivated_account(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(service, "User", _FakeUserModel)
    _FakeUserModel.next_find_one = _FakeUserRecord(
        id="user-1",
        email="candidate@example.com",
        full_name="Jane Candidate",
        password_hash="hash",
        status=UserStatus.DEACTIVATED,
    )
    monkeypatch.setattr(service, "verify_password", lambda *_: True)

    with pytest.raises(HTTPException) as exc_info:
        await service.login_user(
            LoginRequest(email="candidate@example.com", password="StrongPass#2026"),
            Settings(environment="test"),
        )

    assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_login_success_returns_token_and_audits(monkeypatch: pytest.MonkeyPatch) -> None:
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
    monkeypatch.setattr(service, "create_access_token", lambda *_: "signed-token")

    token = await service.login_user(
        LoginRequest(email="candidate@example.com", password="StrongPass#2026"),
        Settings(environment="test"),
    )

    assert token == "signed-token"
    assert _FakeAuditLog.inserted == 1


@pytest.mark.asyncio
async def test_get_user_by_token_returns_none_for_invalid(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(service, "decode_access_token", lambda *_: None)
    monkeypatch.setattr(service, "User", _FakeUserModel)

    result = await service.get_user_by_token("bad", Settings(environment="test"))

    assert result is None
