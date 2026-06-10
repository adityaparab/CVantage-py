"""Admin AI-model settings endpoint tests (issue #62).

Covers RBAC, live-ping key validation on create/rotate, masked output, the
last-active-model-per-usage delete guard, and audit logging.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from beanie import PydanticObjectId
from httpx import ASGITransport, AsyncClient

import app.admin.service as admin_service
from app.auth.dependencies import get_current_user
from app.auth.passwords import hash_password
from app.config import Settings, get_settings
from app.database.models import AuditAction, AuditLog, User, UserRole
from app.main import create_app

_TEST_MASTER_KEY = "MDEyMzQ1Njc4OWFiY2RlZjAxMjM0NTY3ODlhYmNkZWY="


def _settings() -> Settings:
    return Settings(environment="test", master_encryption_key=_TEST_MASTER_KEY)


async def _make_user(*, email: str, role: UserRole = UserRole.CANDIDATE) -> User:
    user = User(email=email, full_name="U", password_hash=hash_password("OldPassw0rd!"), role=role)
    await user.insert()
    return user


def _client_for(user: User) -> AsyncClient:
    async def _current_user() -> User:
        return user

    app = create_app()
    app.dependency_overrides[get_current_user] = _current_user
    app.dependency_overrides[get_settings] = _settings
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


class _ValidatorState:
    valid = True


@pytest_asyncio.fixture
async def models_env(
    beanie_db: object, monkeypatch: pytest.MonkeyPatch
) -> AsyncIterator[AsyncClient]:
    _ValidatorState.valid = True

    async def _fake_validate(provider: str, model: str, key: str, settings: object) -> bool:
        return _ValidatorState.valid

    monkeypatch.setattr(admin_service, "validate_api_key", _fake_validate)
    admin = await _make_user(email="admin@cvantage.io", role=UserRole.ADMIN)
    async with _client_for(admin) as client:
        yield client


async def _create_model(
    client: AsyncClient, *, model_name: str = "gpt-4o", usages: list[str] | None = None
) -> dict[str, object]:
    resp = await client.post(
        "/api/v1/admin/models",
        json={
            "modelName": model_name,
            "provider": "openai",
            "apiKey": "sk-secret-key-1234",
            "usages": usages or ["analysis"],
        },
    )
    assert resp.status_code == 201, resp.text
    body: dict[str, object] = resp.json()
    return body


# ---------------------------------------------------------------------------
# RBAC
# ---------------------------------------------------------------------------


@pytest.mark.usefixtures("beanie_db")
@pytest.mark.asyncio
async def test_candidate_forbidden_on_model_routes() -> None:
    candidate = await _make_user(email="cand@corp.io")
    async with _client_for(candidate) as client:
        assert (await client.get("/api/v1/admin/models")).status_code == 403
        assert (await client.post("/api/v1/admin/models", json={})).status_code == 403


# ---------------------------------------------------------------------------
# Create (with validation) + masking
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_model_masks_key(models_env: AsyncClient) -> None:
    body = await _create_model(models_env)
    assert body["apiKeyLast4"] == "1234"
    assert "apiKey" not in body
    assert "sk-secret-key-1234" not in str(body)

    audit = await AuditLog.find_one({"action": AuditAction.ADMIN_MODEL_ADD.value})
    assert audit is not None


@pytest.mark.asyncio
async def test_create_model_invalid_key_422(models_env: AsyncClient) -> None:
    _ValidatorState.valid = False
    resp = await models_env.post(
        "/api/v1/admin/models",
        json={
            "modelName": "gpt-4o",
            "provider": "openai",
            "apiKey": "sk-bad-key-9999",
            "usages": ["analysis"],
        },
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_model_invalid_usage_422(models_env: AsyncClient) -> None:
    resp = await models_env.post(
        "/api/v1/admin/models",
        json={
            "modelName": "gpt-4o",
            "provider": "openai",
            "apiKey": "sk-secret-key-1234",
            "usages": ["not_a_usage"],
        },
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_list_models_masked(models_env: AsyncClient) -> None:
    await _create_model(models_env)
    listed = await models_env.get("/api/v1/admin/models")
    assert listed.status_code == 200
    body = listed.json()
    assert body["total"] == 1
    assert body["items"][0]["apiKeyLast4"] == "1234"
    assert "sk-secret-key-1234" not in listed.text


# ---------------------------------------------------------------------------
# Update / rotate
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_model_status(models_env: AsyncClient) -> None:
    model = await _create_model(models_env)
    resp = await models_env.patch(
        f"/api/v1/admin/models/{model['id']}", json={"status": "disabled"}
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "disabled"


@pytest.mark.asyncio
async def test_rotate_key_bumps_last4_and_audits(models_env: AsyncClient) -> None:
    model = await _create_model(models_env)
    resp = await models_env.post(
        f"/api/v1/admin/models/{model['id']}/rotate-key",
        json={"apiKey": "sk-rotated-key-8888"},
    )
    assert resp.status_code == 200
    assert resp.json()["apiKeyLast4"] == "8888"

    audit = await AuditLog.find_one({"action": AuditAction.ADMIN_MODEL_KEY_ROTATE.value})
    assert audit is not None


@pytest.mark.asyncio
async def test_rotate_key_invalid_422(models_env: AsyncClient) -> None:
    model = await _create_model(models_env)
    _ValidatorState.valid = False
    resp = await models_env.post(
        f"/api/v1/admin/models/{model['id']}/rotate-key",
        json={"apiKey": "sk-bad-rotate-0000"},
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Delete guard
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_only_active_for_usage_409(models_env: AsyncClient) -> None:
    model = await _create_model(models_env, usages=["analysis"])
    resp = await models_env.request("DELETE", f"/api/v1/admin/models/{model['id']}")
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_delete_allowed_when_another_active_covers_usage(
    models_env: AsyncClient,
) -> None:
    first = await _create_model(models_env, model_name="gpt-4o", usages=["analysis"])
    await _create_model(models_env, model_name="gpt-4o-mini", usages=["analysis"])

    resp = await models_env.request("DELETE", f"/api/v1/admin/models/{first['id']}")
    assert resp.status_code == 200

    audit = await AuditLog.find_one({"action": AuditAction.ADMIN_MODEL_REMOVE.value})
    assert audit is not None


@pytest.mark.asyncio
async def test_delete_unknown_model_404(models_env: AsyncClient) -> None:
    resp = await models_env.request("DELETE", f"/api/v1/admin/models/{PydanticObjectId()}")
    assert resp.status_code == 404
