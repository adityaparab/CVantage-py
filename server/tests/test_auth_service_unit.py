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


def test_oauth_provider_flags_reflect_config() -> None:
    flags = service.oauth_provider_flags(
        Settings(
            environment="test",
            oauth_google_client_id="google-id",
            oauth_google_client_secret="google-secret",
            oauth_linkedin_client_id=None,
            oauth_linkedin_client_secret=None,
        )
    )
    assert flags == {"google": True, "linkedin": False}


@pytest.mark.asyncio
async def test_request_password_reset_is_noop_for_unknown_user(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _FakeUserNone:
        email = object()

        @staticmethod
        async def find_one(*_: object) -> None:
            return None

    called = {"issue": 0, "mail": 0}

    async def _issue(*_: object) -> str:
        called["issue"] += 1
        return "token"

    class _Mailer:
        async def send(self, _: object) -> None:
            called["mail"] += 1

    monkeypatch.setattr(service, "User", _FakeUserNone)
    monkeypatch.setattr(service, "_issue_one_time_token", _issue)
    monkeypatch.setattr(service, "build_mail_service", lambda _: _Mailer())

    await service.request_password_reset("missing@example.com", Settings(environment="test"))

    assert called == {"issue": 0, "mail": 0}


@pytest.mark.asyncio
async def test_request_password_reset_issues_token_and_sends_mail(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = _FakeUserRecord(
        id="user-1",
        email="candidate@example.com",
        full_name="Jane",
        password_hash="hash",
    )

    class _FakeUserByEmail:
        email = object()

        @staticmethod
        async def find_one(*_: object) -> _FakeUserRecord:
            return user

    sent = {"to": None, "subject": None, "body": None}

    async def _issue(*_: object) -> str:
        return "reset-token"

    class _Mailer:
        async def send(self, message: Any) -> None:
            sent["to"] = message.to_email
            sent["subject"] = message.subject
            sent["body"] = message.text_body

    monkeypatch.setattr(service, "User", _FakeUserByEmail)
    monkeypatch.setattr(service, "_issue_one_time_token", _issue)
    monkeypatch.setattr(service, "build_mail_service", lambda _: _Mailer())

    await service.request_password_reset("candidate@example.com", Settings(environment="test"))

    assert sent["to"] == "candidate@example.com"
    assert sent["subject"] == "CVantage password reset"
    assert "reset-token" in cast(str, sent["body"])


@pytest.mark.asyncio
async def test_reset_password_with_token_updates_password_and_revokes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _UserWithSave:
        def __init__(self) -> None:
            self.password_hash = "old"
            self.id = "user-1"
            self.saved = False

        async def save(self) -> None:
            self.saved = True

    user = _UserWithSave()

    @dataclass(slots=True)
    class _TokenRecord:
        user_id: str

    async def _consume(*_: object) -> _TokenRecord:
        return _TokenRecord(user_id="user-1")

    class _UserGet:
        @staticmethod
        async def get(*_: object) -> _UserWithSave:
            return user

    revoked = {"called": False}

    async def _revoke(*_: object) -> None:
        revoked["called"] = True

    monkeypatch.setattr(service, "_consume_one_time_token", _consume)
    monkeypatch.setattr(service, "User", _UserGet)
    monkeypatch.setattr(service, "_revoke_user_refresh_family", _revoke)
    monkeypatch.setattr(service, "hash_password", lambda _: "new-hash")

    await service.reset_password_with_token(
        "token",
        "NewStrongPass#2026",
        Settings(environment="test"),
    )

    assert user.password_hash == "new-hash"
    assert user.saved is True
    assert revoked["called"] is True


@pytest.mark.asyncio
async def test_reset_password_with_token_rejects_missing_user(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    @dataclass(slots=True)
    class _TokenRecord:
        user_id: str

    async def _consume(*_: object) -> _TokenRecord:
        return _TokenRecord(user_id="missing")

    class _MissingUser:
        @staticmethod
        async def get(*_: object) -> None:
            return None

    monkeypatch.setattr(service, "_consume_one_time_token", _consume)
    monkeypatch.setattr(service, "User", _MissingUser)

    with pytest.raises(HTTPException) as exc_info:
        await service.reset_password_with_token(
            "token",
            "NewStrongPass#2026",
            Settings(environment="test"),
        )

    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_verify_email_with_token_marks_user_verified(monkeypatch: pytest.MonkeyPatch) -> None:
    class _UserWithVerify:
        def __init__(self) -> None:
            self.email_verified = False
            self.saved = False

        async def save(self) -> None:
            self.saved = True

    user = _UserWithVerify()

    @dataclass(slots=True)
    class _TokenRecord:
        user_id: str

    async def _consume(*_: object) -> _TokenRecord:
        return _TokenRecord(user_id="user-1")

    class _UserGet:
        @staticmethod
        async def get(*_: object) -> _UserWithVerify:
            return user

    monkeypatch.setattr(service, "_consume_one_time_token", _consume)
    monkeypatch.setattr(service, "User", _UserGet)

    await service.verify_email_with_token("token")

    assert user.email_verified is True
    assert user.saved is True


@pytest.mark.asyncio
async def test_consume_one_time_token_invalid_or_expired(monkeypatch: pytest.MonkeyPatch) -> None:
    class _TokenModel:
        consumed_at: datetime | None = None
        expires_at: datetime

        def __init__(self, expires_at: datetime) -> None:
            self.expires_at = expires_at

        async def save(self) -> None:
            return None

    class _FakeAuthTokenModel:
        next_record: _TokenModel | None = None

        @classmethod
        async def find_one(cls, *_: object) -> _TokenModel | None:
            return cls.next_record

    monkeypatch.setattr(service, "AuthToken", _FakeAuthTokenModel)

    _FakeAuthTokenModel.next_record = None
    with pytest.raises(HTTPException) as missing:
        await service._consume_one_time_token("missing", TokenKind.PASSWORD_RESET)
    assert missing.value.status_code == 400

    _FakeAuthTokenModel.next_record = _TokenModel(
        expires_at=datetime.now(UTC) - timedelta(seconds=1)
    )
    with pytest.raises(HTTPException) as expired:
        await service._consume_one_time_token("expired", TokenKind.PASSWORD_RESET)
    assert expired.value.status_code == 400


@pytest.mark.asyncio
async def test_consume_one_time_token_success_marks_consumed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _TokenModel:
        consumed_at: datetime | None = None
        expires_at: datetime = datetime.now(UTC) + timedelta(hours=1)
        user_id: str = "user-1"

        async def save(self) -> None:
            return None

    record = _TokenModel()

    class _FakeAuthTokenModel:
        @staticmethod
        async def find_one(*_: object) -> _TokenModel:
            return record

    monkeypatch.setattr(service, "AuthToken", _FakeAuthTokenModel)

    consumed = await service._consume_one_time_token("ok-token", TokenKind.EMAIL_VERIFY)

    assert consumed is record
    assert consumed.consumed_at is not None
