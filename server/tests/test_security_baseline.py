import pytest
from httpx import ASGITransport, AsyncClient

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
async def test_auth_route_rate_limit_hits_429_on_61st_request() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        for _ in range(60):
            response = await client.post("/api/v1/auth/login")
            assert response.status_code == 200

        blocked = await client.post("/api/v1/auth/login")

    body = blocked.json()
    assert blocked.status_code == 429
    assert body["status_code"] == 429
    assert body["error"] == "Too Many Requests"
