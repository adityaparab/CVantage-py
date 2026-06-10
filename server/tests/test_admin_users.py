"""Admin user-management endpoint tests (issue #60).

Covers the RBAC denial matrix, search/pagination, update with uniqueness,
password reset (temp + email), and deactivate/reactivate with session
revocation and audit logging.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
from beanie import PydanticObjectId
from httpx import ASGITransport, AsyncClient

from app.auth.dependencies import get_current_user
from app.auth.passwords import hash_password
from app.database.models import (
    AuditAction,
    AuditLog,
    AuthToken,
    TokenKind,
    User,
    UserRole,
    UserStatus,
)
from app.main import create_app


async def _make_user(
    *,
    email: str,
    full_name: str = "Test User",
    role: UserRole = UserRole.CANDIDATE,
    status: UserStatus = UserStatus.ACTIVE,
) -> User:
    user = User(
        email=email,
        full_name=full_name,
        password_hash=hash_password("OldPassw0rd!"),
        role=role,
        status=status,
    )
    await user.insert()
    return user


def _client_for(user: User) -> AsyncClient:
    async def _current_user() -> User:
        return user

    app = create_app()
    app.dependency_overrides[get_current_user] = _current_user
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest_asyncio.fixture
async def admin_env(
    beanie_db: object,
) -> AsyncIterator[tuple[AsyncClient, User]]:
    admin = await _make_user(email="admin@cvantage.io", full_name="Admin", role=UserRole.ADMIN)
    async with _client_for(admin) as client:
        yield client, admin


# ---------------------------------------------------------------------------
# RBAC denial matrix
# ---------------------------------------------------------------------------

_ADMIN_USER_ROUTES = [
    ("GET", "/api/v1/admin/users"),
    ("GET", "/api/v1/admin/users/{id}"),
    ("PATCH", "/api/v1/admin/users/{id}"),
    ("POST", "/api/v1/admin/users/{id}/reset-password"),
    ("POST", "/api/v1/admin/users/{id}/deactivate"),
    ("POST", "/api/v1/admin/users/{id}/reactivate"),
]


@pytest.mark.usefixtures("beanie_db")
@pytest.mark.parametrize(("method", "path"), _ADMIN_USER_ROUTES)
@pytest.mark.asyncio
async def test_candidate_forbidden_on_admin_routes(method: str, path: str) -> None:
    candidate = await _make_user(email="cand@cvantage.io", role=UserRole.CANDIDATE)
    target = await _make_user(email="target@cvantage.io")
    url = path.format(id=target.id)
    async with _client_for(candidate) as client:
        resp = await client.request(method, url, json={})
    assert resp.status_code == 403


@pytest.mark.usefixtures("beanie_db")
@pytest.mark.parametrize(("method", "path"), _ADMIN_USER_ROUTES)
@pytest.mark.asyncio
async def test_anonymous_unauthorized_on_admin_routes(method: str, path: str) -> None:
    url = path.format(id=PydanticObjectId())
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.request(method, url, json={})
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# List / search / pagination
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_users_and_search(admin_env: tuple[AsyncClient, User]) -> None:
    client, _ = admin_env
    await _make_user(email="alice@corp.io", full_name="Alice Anderson")
    await _make_user(email="bob@corp.io", full_name="Bob Brown")

    listed = await client.get("/api/v1/admin/users")
    assert listed.status_code == 200
    body = listed.json()
    # admin + alice + bob
    assert body["total"] == 3

    by_email = await client.get("/api/v1/admin/users", params={"search": "alice@corp"})
    assert by_email.json()["total"] == 1
    assert by_email.json()["items"][0]["fullName"] == "Alice Anderson"

    by_name = await client.get("/api/v1/admin/users", params={"search": "Brown"})
    assert by_name.json()["total"] == 1
    assert by_name.json()["items"][0]["email"] == "bob@corp.io"


@pytest.mark.asyncio
async def test_get_user_detail_and_404(admin_env: tuple[AsyncClient, User]) -> None:
    client, _ = admin_env
    target = await _make_user(email="detail@corp.io", full_name="Detail User")
    ok = await client.get(f"/api/v1/admin/users/{target.id}")
    assert ok.status_code == 200
    assert ok.json()["email"] == "detail@corp.io"

    missing = await client.get(f"/api/v1/admin/users/{PydanticObjectId()}")
    assert missing.status_code == 404


# ---------------------------------------------------------------------------
# Update
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_user_name_and_email(admin_env: tuple[AsyncClient, User]) -> None:
    client, _ = admin_env
    target = await _make_user(email="old@corp.io", full_name="Old Name")
    resp = await client.patch(
        f"/api/v1/admin/users/{target.id}",
        json={"fullName": "New Name", "email": "new@corp.io"},
    )
    assert resp.status_code == 200
    assert resp.json()["fullName"] == "New Name"
    assert resp.json()["email"] == "new@corp.io"

    audit = await AuditLog.find_one({"action": AuditAction.ADMIN_USER_UPDATE.value})
    assert audit is not None


@pytest.mark.asyncio
async def test_update_user_email_collision_409(admin_env: tuple[AsyncClient, User]) -> None:
    client, _ = admin_env
    await _make_user(email="taken@corp.io")
    target = await _make_user(email="mover@corp.io")
    resp = await client.patch(f"/api/v1/admin/users/{target.id}", json={"email": "taken@corp.io"})
    assert resp.status_code == 409


# ---------------------------------------------------------------------------
# Password reset
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_reset_password_temp_revokes_sessions(
    admin_env: tuple[AsyncClient, User],
) -> None:
    client, _ = admin_env
    target = await _make_user(email="reset@corp.io")
    old_hash = target.password_hash
    # Seed an active refresh token that must be revoked.
    token = AuthToken(
        user_id=target.id,
        kind=TokenKind.REFRESH,
        token_hash="active-refresh-hash",
        expires_at=datetime.now(UTC) + timedelta(days=30),
    )
    await token.insert()

    resp = await client.post(
        f"/api/v1/admin/users/{target.id}/reset-password",
        json={"newPassword": "BrandNewPass1!"},
    )
    assert resp.status_code == 200
    assert resp.json()["method"] == "temp_password"

    refreshed = await User.get(target.id)
    assert refreshed is not None
    assert refreshed.password_hash != old_hash
    revoked = await AuthToken.get(token.id)
    assert revoked is not None and revoked.consumed_at is not None


@pytest.mark.asyncio
async def test_reset_password_email_path(admin_env: tuple[AsyncClient, User]) -> None:
    client, _ = admin_env
    target = await _make_user(email="mailme@corp.io")
    resp = await client.post(f"/api/v1/admin/users/{target.id}/reset-password", json={})
    assert resp.status_code == 200
    assert resp.json()["method"] == "reset_email"
    audit = await AuditLog.find_one({"action": AuditAction.ADMIN_PASSWORD_RESET.value})
    assert audit is not None


# ---------------------------------------------------------------------------
# Deactivate / reactivate
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_deactivate_revokes_tokens_and_audits(
    admin_env: tuple[AsyncClient, User],
) -> None:
    client, _ = admin_env
    target = await _make_user(email="deact@corp.io")
    token = AuthToken(
        user_id=target.id,
        kind=TokenKind.REFRESH,
        token_hash="deact-refresh-hash",
        expires_at=datetime.now(UTC) + timedelta(days=30),
    )
    await token.insert()

    resp = await client.post(f"/api/v1/admin/users/{target.id}/deactivate")
    assert resp.status_code == 200

    refreshed = await User.get(target.id)
    assert refreshed is not None
    assert refreshed.status == UserStatus.DEACTIVATED
    revoked = await AuthToken.get(token.id)
    assert revoked is not None and revoked.consumed_at is not None
    audit = await AuditLog.find_one({"action": AuditAction.ADMIN_USER_DEACTIVATE.value})
    assert audit is not None


@pytest.mark.asyncio
async def test_admin_cannot_deactivate_self(admin_env: tuple[AsyncClient, User]) -> None:
    client, admin = admin_env
    resp = await client.post(f"/api/v1/admin/users/{admin.id}/deactivate")
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_reactivate_restores_user(admin_env: tuple[AsyncClient, User]) -> None:
    client, _ = admin_env
    target = await _make_user(email="react@corp.io", status=UserStatus.DEACTIVATED)
    resp = await client.post(f"/api/v1/admin/users/{target.id}/reactivate")
    assert resp.status_code == 200
    refreshed = await User.get(target.id)
    assert refreshed is not None
    assert refreshed.status == UserStatus.ACTIVE
    audit = await AuditLog.find_one({"action": AuditAction.ADMIN_USER_REACTIVATE.value})
    assert audit is not None
