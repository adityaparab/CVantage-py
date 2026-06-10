from __future__ import annotations

from typing import Any

import pytest
from pymongo import IndexModel
from typer.testing import CliRunner

import app.cli as cli_module
from app.auth import verify_password
from app.config import Settings


class _Field:
    def __eq__(self, other: object) -> bool:
        _ = other
        return True


class _FakeExistingAdmin:
    def __init__(self) -> None:
        self.email = "admin@example.com"


class _FakeUser:
    email = _Field()
    existing: _FakeExistingAdmin | None = None
    inserted: list[_FakeUser] = []

    def __init__(self, **kwargs: Any) -> None:
        self.kwargs = kwargs
        self.password_hash = kwargs.get("password_hash")

    async def insert(self) -> None:
        self.__class__.inserted.append(self)

    @classmethod
    async def find_one(cls, _: object) -> _FakeExistingAdmin | None:
        return cls.existing


class _FakeCollection:
    def __init__(self, indexes: dict[str, dict[str, object]]) -> None:
        self._indexes = indexes

    async def index_information(self) -> dict[str, dict[str, object]]:
        return self._indexes


class _FakeSettingsObj:
    def __init__(self, name: str) -> None:
        self.name = name


class _FakeModel:
    class Settings:
        indexes = [IndexModel([("email", 1)], name="uniq_email_ci")]

    @staticmethod
    def get_settings() -> _FakeSettingsObj:
        return _FakeSettingsObj("users")

    @staticmethod
    def get_motor_collection() -> _FakeCollection:
        return _FakeCollection({"_id_": {}, "uniq_email_ci": {}})


@pytest.mark.asyncio
async def test_seed_admin_is_idempotent(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _init_database(_: Settings) -> None:
        return None

    async def _close_database() -> None:
        return None

    _FakeUser.existing = None
    _FakeUser.inserted = []

    monkeypatch.setattr(cli_module, "init_database", _init_database)
    monkeypatch.setattr(cli_module, "close_database", _close_database)
    monkeypatch.setattr(cli_module, "User", _FakeUser)

    settings = Settings(
        environment="test",
        admin_email="admin@example.com",
        admin_password="super-secret-password",
    )

    first_created = await cli_module.seed_admin_account(settings)
    assert first_created is True
    assert len(_FakeUser.inserted) == 1

    inserted_hash = _FakeUser.inserted[0].password_hash
    assert isinstance(inserted_hash, str)
    assert inserted_hash != settings.admin_password
    assert settings.admin_password is not None
    assert verify_password(settings.admin_password, inserted_hash)

    _FakeUser.existing = _FakeExistingAdmin()
    second_created = await cli_module.seed_admin_account(settings)

    assert second_created is False
    assert len(_FakeUser.inserted) == 1


@pytest.mark.asyncio
async def test_seed_admin_requires_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _init_database(_: Settings) -> None:
        return None

    async def _close_database() -> None:
        return None

    monkeypatch.setattr(cli_module, "init_database", _init_database)
    monkeypatch.setattr(cli_module, "close_database", _close_database)

    with pytest.raises(ValueError):
        await cli_module.seed_admin_account(Settings(environment="test"))


@pytest.mark.asyncio
async def test_sync_indexes_reports_expected_names(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _init_database(_: Settings) -> None:
        return None

    async def _close_database() -> None:
        return None

    monkeypatch.setattr(cli_module, "init_database", _init_database)
    monkeypatch.setattr(cli_module, "close_database", _close_database)
    monkeypatch.setattr(cli_module, "DOCUMENT_MODELS", [_FakeModel])

    statuses = await cli_module.collect_index_sync_status(Settings(environment="test"))

    assert len(statuses) == 1
    assert statuses[0].collection == "users"
    assert statuses[0].expected == ["uniq_email_ci"]
    assert statuses[0].missing == []


def test_seed_admin_cli_happy_path(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _seed_admin_account(_: Settings) -> bool:
        return True

    monkeypatch.setattr(cli_module, "seed_admin_account", _seed_admin_account)
    monkeypatch.setattr(
        cli_module,
        "get_settings",
        lambda: Settings(
            environment="test",
            admin_email="admin@example.com",
            admin_password="pw",
        ),
    )

    runner = CliRunner()
    result = runner.invoke(cli_module.cli, ["seed-admin"])

    assert result.exit_code == 0
    assert "Admin user created" in result.stdout


def test_seed_admin_cli_missing_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _seed_admin_account(_: Settings) -> bool:
        raise ValueError("ADMIN_EMAIL and ADMIN_PASSWORD must be set")

    monkeypatch.setattr(cli_module, "seed_admin_account", _seed_admin_account)
    monkeypatch.setattr(cli_module, "get_settings", lambda: Settings(environment="test"))

    runner = CliRunner()
    result = runner.invoke(cli_module.cli, ["seed-admin"])

    assert result.exit_code == 1
    assert "ADMIN_EMAIL and ADMIN_PASSWORD must be set" in result.stdout


def test_sync_indexes_cli_outputs_summary(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _collect_index_sync_status(_: Settings) -> list[cli_module.IndexSyncStatus]:
        return [
            cli_module.IndexSyncStatus(
                collection="users",
                expected=["uniq_email_ci"],
                existing=["_id_", "uniq_email_ci"],
                missing=[],
            )
        ]

    monkeypatch.setattr(cli_module, "collect_index_sync_status", _collect_index_sync_status)
    monkeypatch.setattr(cli_module, "get_settings", lambda: Settings(environment="test"))

    runner = CliRunner()
    result = runner.invoke(cli_module.cli, ["sync-indexes"])

    assert result.exit_code == 0
    assert "users: 2 indexes" in result.stdout
