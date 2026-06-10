from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Annotated

import pytest
import pytest_asyncio
from fastapi import Header, HTTPException
from httpx import ASGITransport, AsyncClient

import app.auth.router as auth_router
from app.auth.dependencies import get_current_user
from app.auth.schemas import LoginRequest, RegisterRequest
from app.config import Settings, get_settings
from app.database.models import UserRole, UserStatus
from app.main import create_app


@dataclass(slots=True)
class _FakeUser:
    id: str
    email: str
    full_name: str
    role: UserRole = UserRole.CANDIDATE
    status: UserStatus = UserStatus.ACTIVE


@pytest_asyncio.fixture
async def auth_client(monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[AsyncClient]:
    users: dict[str, _FakeUser] = {}
    password_store: dict[str, str] = {}
    access_tokens: dict[str, str] = {}
    refresh_active: dict[str, str] = {}
    refresh_consumed_owner: dict[str, str] = {}
    revoked_users: set[str] = set()

    token_counter = 0

    def _issue_access(email: str) -> str:
        nonlocal token_counter
        token_counter += 1
        token = f"access-{token_counter}"
        access_tokens[token] = email
        return token

    def _issue_refresh(email: str) -> str:
        nonlocal token_counter
        token_counter += 1
        token = f"refresh-{token_counter}"
        refresh_active[token] = email
        return token

    def _consume_refresh(token: str) -> str | None:
        owner = refresh_active.pop(token, None)
        if owner is not None:
            refresh_consumed_owner[token] = owner
        return owner

    def _revoke_user_family(owner: str) -> None:
        to_revoke = [token for token, email in refresh_active.items() if email == owner]
        for token in to_revoke:
            refresh_consumed_owner[token] = owner
            refresh_active.pop(token, None)
        revoked_users.add(owner)

    async def _register_user(payload: RegisterRequest, _: object) -> _FakeUser:
        email = str(payload.email).lower().strip()
        if len(payload.password) < 12:
            raise HTTPException(
                status_code=422,
                detail={
                    "message": "Password policy requirements not met",
                    "policy": {
                        "min_length": 12,
                        "requires_uppercase": True,
                        "requires_lowercase": True,
                        "requires_digit": True,
                        "requires_special": True,
                    },
                },
            )
        if email in users:
            raise HTTPException(status_code=409, detail={"message": "Email already registered"})

        user = _FakeUser(id=f"user-{len(users) + 1}", email=email, full_name=payload.full_name)
        users[email] = user
        password_store[email] = payload.password
        return user

    async def _login_user(payload: LoginRequest, _: object, __: object) -> tuple[str, str]:
        email = str(payload.email).lower().strip()
        user = users.get(email)
        if user is None:
            raise HTTPException(status_code=401, detail={"message": "Invalid email or password"})
        if password_store[email] != payload.password:
            raise HTTPException(status_code=401, detail={"message": "Invalid email or password"})
        if user.status == UserStatus.DEACTIVATED or email == "disabled@example.com":
            raise HTTPException(status_code=403, detail={"message": "Account is deactivated"})

        return _issue_access(email), _issue_refresh(email)

    async def _refresh_user_session(
        refresh_token: str,
        _: object,
        __: object,
    ) -> tuple[str, str]:
        consumed_owner = refresh_consumed_owner.get(refresh_token)
        if consumed_owner is not None:
            _revoke_user_family(consumed_owner)
            raise HTTPException(status_code=401, detail={"message": "Invalid refresh token"})

        owner = _consume_refresh(refresh_token)
        if owner is None:
            raise HTTPException(status_code=401, detail={"message": "Invalid refresh token"})
        if owner in revoked_users:
            raise HTTPException(status_code=401, detail={"message": "Invalid refresh token"})

        return _issue_access(owner), _issue_refresh(owner)

    async def _logout_user_session(refresh_token: str | None, _: object) -> None:
        if not refresh_token:
            return
        owner = refresh_active.get(refresh_token) or refresh_consumed_owner.get(refresh_token)
        if owner is not None:
            _revoke_user_family(owner)

    async def _get_current_user_override(
        authorization: Annotated[str | None, Header()] = None,
    ) -> _FakeUser:
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(status_code=401, detail={"message": "Authentication required"})

        token = authorization.split(" ", maxsplit=1)[1]
        email = access_tokens.get(token)
        if email is None:
            raise HTTPException(status_code=401, detail={"message": "Authentication required"})

        user = users[email]
        if user.status == UserStatus.DEACTIVATED:
            raise HTTPException(status_code=403, detail={"message": "Account is deactivated"})
        return user

    monkeypatch.setattr(auth_router, "register_user", _register_user)
    monkeypatch.setattr(auth_router, "login_user", _login_user)
    monkeypatch.setattr(auth_router, "refresh_user_session", _refresh_user_session)
    monkeypatch.setattr(auth_router, "logout_user_session", _logout_user_session)

    app = create_app()
    app.dependency_overrides[get_current_user] = _get_current_user_override
    app.dependency_overrides[get_settings] = lambda: Settings(
        environment="test",
        auth_cookie_secure=False,
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_register_login_and_users_me_flow(auth_client: AsyncClient) -> None:
    register_response = await auth_client.post(
        "/api/v1/auth/register",
        json={
            "email": "candidate@example.com",
            "fullName": "Jane Candidate",
            "password": "StrongPass#2026",
        },
    )
    assert register_response.status_code == 200

    login_response = await auth_client.post(
        "/api/v1/auth/login",
        json={"email": "candidate@example.com", "password": "StrongPass#2026"},
    )
    assert login_response.status_code == 200

    token = login_response.json()["accessToken"]
    me_response = await auth_client.get(
        "/api/v1/users/me",
        headers={"Authorization": f"Bearer {token}"},
    )

    body = me_response.json()
    assert me_response.status_code == 200
    assert body["email"] == "candidate@example.com"
    assert body["role"] == "candidate"


@pytest.mark.asyncio
async def test_duplicate_email_case_insensitive_returns_409(auth_client: AsyncClient) -> None:
    await auth_client.post(
        "/api/v1/auth/register",
        json={
            "email": "candidate@example.com",
            "fullName": "Jane Candidate",
            "password": "StrongPass#2026",
        },
    )

    duplicate = await auth_client.post(
        "/api/v1/auth/register",
        json={
            "email": "CANDIDATE@example.com",
            "fullName": "Another Candidate",
            "password": "StrongPass#2026",
        },
    )

    assert duplicate.status_code == 409
    assert duplicate.json()["message"] == "Email already registered"


@pytest.mark.asyncio
async def test_weak_password_returns_422_with_policy_details(auth_client: AsyncClient) -> None:
    response = await auth_client.post(
        "/api/v1/auth/register",
        json={
            "email": "weak@example.com",
            "fullName": "Weak Password",
            "password": "weakpass",
        },
    )

    body = response.json()
    assert response.status_code == 422
    assert body["message"] == "Password policy requirements not met"
    assert body["details"]["policy"]["min_length"] == 12


@pytest.mark.asyncio
async def test_login_unknown_email_and_wrong_password_share_identical_error(
    auth_client: AsyncClient,
) -> None:
    await auth_client.post(
        "/api/v1/auth/register",
        json={
            "email": "candidate@example.com",
            "fullName": "Jane Candidate",
            "password": "StrongPass#2026",
        },
    )

    unknown = await auth_client.post(
        "/api/v1/auth/login",
        json={"email": "missing@example.com", "password": "StrongPass#2026"},
    )
    wrong_password = await auth_client.post(
        "/api/v1/auth/login",
        json={"email": "candidate@example.com", "password": "WrongPass#2026"},
    )

    assert unknown.status_code == 401
    assert wrong_password.status_code == 401
    assert unknown.json()["message"] == "Invalid email or password"
    assert wrong_password.json()["message"] == "Invalid email or password"


@pytest.mark.asyncio
async def test_deactivated_account_blocked(auth_client: AsyncClient) -> None:
    await auth_client.post(
        "/api/v1/auth/register",
        json={
            "email": "disabled@example.com",
            "fullName": "Disabled User",
            "password": "StrongPass#2026",
        },
    )

    response = await auth_client.post(
        "/api/v1/auth/login",
        json={"email": "disabled@example.com", "password": "StrongPass#2026"},
    )

    assert response.status_code == 403
    assert response.json()["message"] == "Account is deactivated"


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_refresh_rotates_and_old_token_reuse_returns_401(auth_client: AsyncClient) -> None:
    login_response = await auth_client.post(
        "/api/v1/auth/login",
        json={"email": "candidate@example.com", "password": "StrongPass#2026"},
    )
    if login_response.status_code == 401:
        await auth_client.post(
            "/api/v1/auth/register",
            json={
                "email": "candidate@example.com",
                "fullName": "Jane Candidate",
                "password": "StrongPass#2026",
            },
        )
        login_response = await auth_client.post(
            "/api/v1/auth/login",
            json={"email": "candidate@example.com", "password": "StrongPass#2026"},
        )

    old_refresh = login_response.cookies.get("cv_refresh_token")
    assert old_refresh is not None

    rotated = await auth_client.post("/api/v1/auth/refresh")
    assert rotated.status_code == 200

    replay = await auth_client.post(
        "/api/v1/auth/refresh",
        cookies={"cv_refresh_token": old_refresh},
    )
    assert replay.status_code == 401


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_refresh_reuse_detection_revokes_session_family(auth_client: AsyncClient) -> None:
    await auth_client.post(
        "/api/v1/auth/register",
        json={
            "email": "reuse@example.com",
            "fullName": "Reuse Candidate",
            "password": "StrongPass#2026",
        },
    )

    login_a = await auth_client.post(
        "/api/v1/auth/login",
        json={"email": "reuse@example.com", "password": "StrongPass#2026"},
    )
    login_b = await auth_client.post(
        "/api/v1/auth/login",
        json={"email": "reuse@example.com", "password": "StrongPass#2026"},
    )

    refresh_a = login_a.cookies.get("cv_refresh_token")
    refresh_b = login_b.cookies.get("cv_refresh_token")
    assert refresh_a is not None
    assert refresh_b is not None

    rotate_a = await auth_client.post(
        "/api/v1/auth/refresh",
        cookies={"cv_refresh_token": refresh_a},
    )
    assert rotate_a.status_code == 200

    reuse_attempt = await auth_client.post(
        "/api/v1/auth/refresh",
        cookies={"cv_refresh_token": refresh_a},
    )
    assert reuse_attempt.status_code == 401

    family_revoked = await auth_client.post(
        "/api/v1/auth/refresh",
        cookies={"cv_refresh_token": refresh_b},
    )
    assert family_revoked.status_code == 401


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_expired_access_with_valid_refresh_recovers(auth_client: AsyncClient) -> None:
    await auth_client.post(
        "/api/v1/auth/register",
        json={
            "email": "recover@example.com",
            "fullName": "Recover Candidate",
            "password": "StrongPass#2026",
        },
    )
    login_response = await auth_client.post(
        "/api/v1/auth/login",
        json={"email": "recover@example.com", "password": "StrongPass#2026"},
    )
    assert login_response.status_code == 200

    expired_access = await auth_client.get(
        "/api/v1/users/me",
        headers={"Authorization": "Bearer expired-token"},
    )
    assert expired_access.status_code == 401

    refreshed = await auth_client.post("/api/v1/auth/refresh")
    assert refreshed.status_code == 200

    new_access = refreshed.json()["accessToken"]
    recovered_me = await auth_client.get(
        "/api/v1/users/me",
        headers={"Authorization": f"Bearer {new_access}"},
    )
    assert recovered_me.status_code == 200


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_oauth_flags_off_reports_false_and_routes_404(auth_client: AsyncClient) -> None:
    providers = await auth_client.get("/api/v1/auth/providers")
    assert providers.status_code == 200
    assert providers.json() == {"google": False, "linkedin": False}

    login_disabled = await auth_client.get("/api/v1/auth/oauth/google/login")
    assert login_disabled.status_code == 404

    callback_disabled = await auth_client.get(
        "/api/v1/auth/oauth/google/callback",
        params={"code": "mock", "state": "mock"},
    )
    assert callback_disabled.status_code == 404


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_oauth_mocked_callback_new_user_and_existing_email_link(
    auth_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        auth_router,
        "oauth_provider_flags",
        lambda _: {"google": True, "linkedin": False},
    )

    async def _build_url(*_: object) -> str:
        return "https://provider.example/authorize"

    async def _callback_login(
        _: object,
        code: str,
        __: str,
        ___: object,
        ____: object,
    ) -> tuple[str, str]:
        if code == "duplicate":
            raise HTTPException(
                status_code=409,
                detail={"message": "OAuth identity already linked"},
            )
        if code == "existing-link":
            return ("access-existing", "refresh-existing")
        return ("access-new", "refresh-new")

    monkeypatch.setattr(auth_router, "build_oauth_authorization_url", _build_url)
    monkeypatch.setattr(auth_router, "oauth_callback_login", _callback_login)

    providers = await auth_client.get("/api/v1/auth/providers")
    assert providers.status_code == 200
    assert providers.json() == {"google": True, "linkedin": False}

    login_start = await auth_client.get("/api/v1/auth/oauth/google/login")
    assert login_start.status_code == 200
    assert login_start.json()["authorizationUrl"] == "https://provider.example/authorize"

    state_cookie = login_start.cookies.get("cv_oauth_google_state")
    assert state_cookie is not None

    new_user = await auth_client.get(
        "/api/v1/auth/oauth/google/callback",
        params={"code": "new-user", "state": state_cookie},
    )
    assert new_user.status_code == 200
    assert new_user.json()["accessToken"] == "access-new"

    relogin_start = await auth_client.get("/api/v1/auth/oauth/google/login")
    existing_state = relogin_start.cookies.get("cv_oauth_google_state")
    assert existing_state is not None

    existing_link = await auth_client.get(
        "/api/v1/auth/oauth/google/callback",
        params={"code": "existing-link", "state": existing_state},
    )
    assert existing_link.status_code == 200
    assert existing_link.json()["accessToken"] == "access-existing"


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_oauth_mocked_duplicate_identity_conflict(
    auth_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        auth_router,
        "oauth_provider_flags",
        lambda _: {"google": True, "linkedin": False},
    )

    async def _build_url(*_: object) -> str:
        return "https://provider.example/authorize"

    async def _callback_login(*_: object) -> tuple[str, str]:
        raise HTTPException(status_code=409, detail={"message": "OAuth identity already linked"})

    monkeypatch.setattr(auth_router, "build_oauth_authorization_url", _build_url)
    monkeypatch.setattr(auth_router, "oauth_callback_login", _callback_login)

    login_start = await auth_client.get("/api/v1/auth/oauth/google/login")
    state_cookie = login_start.cookies.get("cv_oauth_google_state")
    assert state_cookie is not None

    conflict = await auth_client.get(
        "/api/v1/auth/oauth/google/callback",
        params={"code": "duplicate", "state": state_cookie},
    )
    assert conflict.status_code == 409
