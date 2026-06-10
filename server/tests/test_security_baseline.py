import pytest
from httpx import ASGITransport, AsyncClient

import app.auth.router as auth_router
from app.main import app


@pytest.mark.asyncio
async def test_security_headers_present_on_api_response() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/health/live")

    assert response.status_code == 200
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["referrer-policy"] == "no-referrer"
    assert response.headers["content-security-policy"] == "default-src 'self'"


@pytest.mark.asyncio
async def test_cors_disallowed_origin_is_blocked() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.options(
            "/api/v1/health/live",
            headers={
                "Origin": "http://evil.example",
                "Access-Control-Request-Method": "GET",
            },
        )

    assert response.status_code == 400
    assert "access-control-allow-origin" not in response.headers


@pytest.mark.asyncio
async def test_auth_route_rate_limit_hits_429_on_61st_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _fake_login_user(_: object, __: object, ___: object) -> tuple[str, str]:
        return "access", "refresh"

    monkeypatch.setattr(auth_router, "login_user", _fake_login_user)

    payload = {"email": "rate-limit@example.com", "password": "StrongPass#2026"}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        responses = []
        for _ in range(61):
            responses.append(await client.post("/api/v1/auth/login", json=payload))

    assert any(response.status_code == 429 for response in responses)
    blocked = next(response for response in responses if response.status_code == 429)

    body = blocked.json()
    assert blocked.status_code == 429
    assert body["status_code"] == 429
    assert body["error"] == "Too Many Requests"
