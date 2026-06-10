"""Consolidated admin RBAC denial matrix (issue #63).

Exercises the *real* auth dependency (no override) with issued JWTs so the full
matrix is proven: anonymous -> 401, candidate -> 403, deactivated admin -> 403,
active admin -> 200.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from beanie import PydanticObjectId
from httpx import ASGITransport, AsyncClient

from app.auth.passwords import hash_password
from app.auth.tokens import create_access_token
from app.config import Settings
from app.database.models import User, UserRole, UserStatus
from app.main import create_app

_DUMMY_ID = PydanticObjectId()

# Representative routes covering every admin handler family. The role guard and
# get_current_user run before any handler body, so denial is uniform.
_ADMIN_ROUTES = [
    ("GET", "/api/v1/admin/stats"),
    ("GET", "/api/v1/admin/users"),
    ("GET", f"/api/v1/admin/users/{_DUMMY_ID}"),
    ("PATCH", f"/api/v1/admin/users/{_DUMMY_ID}"),
    ("POST", f"/api/v1/admin/users/{_DUMMY_ID}/reset-password"),
    ("POST", f"/api/v1/admin/users/{_DUMMY_ID}/deactivate"),
    ("POST", f"/api/v1/admin/users/{_DUMMY_ID}/reactivate"),
    ("GET", f"/api/v1/admin/users/{_DUMMY_ID}/resumes"),
    ("DELETE", f"/api/v1/admin/resumes/{_DUMMY_ID}"),
    ("GET", "/api/v1/admin/models"),
    ("POST", "/api/v1/admin/models"),
    ("PATCH", f"/api/v1/admin/models/{_DUMMY_ID}"),
    ("POST", f"/api/v1/admin/models/{_DUMMY_ID}/rotate-key"),
    ("DELETE", f"/api/v1/admin/models/{_DUMMY_ID}"),
]


async def _make_user(*, email: str, role: UserRole, status: UserStatus) -> User:
    user = User(
        email=email,
        full_name="U",
        password_hash=hash_password("OldPassw0rd!"),
        role=role,
        status=status,
    )
    await user.insert()
    return user


def _token(user: User) -> str:
    return create_access_token(str(user.id), Settings())


@pytest_asyncio.fixture
async def matrix_env(
    beanie_db: object,
) -> AsyncIterator[tuple[AsyncClient, dict[str, str]]]:
    candidate = await _make_user(
        email="cand@cvantage.io", role=UserRole.CANDIDATE, status=UserStatus.ACTIVE
    )
    deactivated_admin = await _make_user(
        email="exadmin@cvantage.io", role=UserRole.ADMIN, status=UserStatus.DEACTIVATED
    )
    active_admin = await _make_user(
        email="admin@cvantage.io", role=UserRole.ADMIN, status=UserStatus.ACTIVE
    )
    tokens = {
        "candidate": _token(candidate),
        "deactivated_admin": _token(deactivated_admin),
        "active_admin": _token(active_admin),
    }
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client, tokens


@pytest.mark.parametrize(("method", "path"), _ADMIN_ROUTES)
@pytest.mark.asyncio
async def test_anonymous_is_401(
    matrix_env: tuple[AsyncClient, dict[str, str]], method: str, path: str
) -> None:
    client, _ = matrix_env
    resp = await client.request(method, path, json={})
    assert resp.status_code == 401


@pytest.mark.parametrize(("method", "path"), _ADMIN_ROUTES)
@pytest.mark.asyncio
async def test_candidate_is_403(
    matrix_env: tuple[AsyncClient, dict[str, str]], method: str, path: str
) -> None:
    client, tokens = matrix_env
    headers = {"Authorization": f"Bearer {tokens['candidate']}"}
    resp = await client.request(method, path, json={}, headers=headers)
    assert resp.status_code == 403


@pytest.mark.parametrize(("method", "path"), _ADMIN_ROUTES)
@pytest.mark.asyncio
async def test_deactivated_admin_is_403(
    matrix_env: tuple[AsyncClient, dict[str, str]], method: str, path: str
) -> None:
    client, tokens = matrix_env
    headers = {"Authorization": f"Bearer {tokens['deactivated_admin']}"}
    resp = await client.request(method, path, json={}, headers=headers)
    # Deactivated accounts are rejected by get_current_user even with a valid JWT.
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_active_admin_allowed_on_read_routes(
    matrix_env: tuple[AsyncClient, dict[str, str]],
) -> None:
    client, tokens = matrix_env
    headers = {"Authorization": f"Bearer {tokens['active_admin']}"}
    # Routes that do not require provider crypto config.
    for path in ("/api/v1/admin/stats", "/api/v1/admin/users"):
        resp = await client.get(path, headers=headers)
        assert resp.status_code == 200
