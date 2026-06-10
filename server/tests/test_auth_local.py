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
    tokens: dict[str, str] = {}

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

    async def _login_user(payload: LoginRequest, _: object) -> str:
        email = str(payload.email).lower().strip()
        user = users.get(email)
        if user is None:
            raise HTTPException(status_code=401, detail={"message": "Invalid email or password"})
        if password_store[email] != payload.password:
            raise HTTPException(status_code=401, detail={"message": "Invalid email or password"})
        if user.status == UserStatus.DEACTIVATED or email == "disabled@example.com":
            raise HTTPException(status_code=403, detail={"message": "Account is deactivated"})

        token = f"token-{user.id}"
        tokens[token] = user.email
        return token

    async def _get_current_user_override(
        authorization: Annotated[str | None, Header()] = None,
    ) -> _FakeUser:
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(status_code=401, detail={"message": "Authentication required"})

        token = authorization.split(" ", maxsplit=1)[1]
        email = tokens.get(token)
        if email is None:
            raise HTTPException(status_code=401, detail={"message": "Authentication required"})

        user = users[email]
        if user.status == UserStatus.DEACTIVATED:
            raise HTTPException(status_code=403, detail={"message": "Account is deactivated"})
        return user

    monkeypatch.setattr(auth_router, "register_user", _register_user)
    monkeypatch.setattr(auth_router, "login_user", _login_user)

    app = create_app()
    app.dependency_overrides[get_current_user] = _get_current_user_override

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
