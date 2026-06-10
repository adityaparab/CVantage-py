import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_validation_error_uses_problem_details_envelope() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/health/number?value=abc")

    data = response.json()
    assert response.status_code == 422
    assert data["status_code"] == 422
    assert data["error"] == "Validation Error"
    assert data["message"] == "Request validation failed"
    assert isinstance(data.get("details"), list)


@pytest.mark.asyncio
async def test_unhandled_exception_returns_500_envelope() -> None:
    route_path = "/api/v1/test-unhandled-error"

    if not any(getattr(route, "path", None) == route_path for route in app.routes):

        @app.get(route_path)
        async def _boom() -> dict[str, str]:
            raise RuntimeError("boom")

    async with AsyncClient(
        transport=ASGITransport(app=app, raise_app_exceptions=False),
        base_url="http://test",
    ) as client:
        response = await client.get(route_path)

    data = response.json()
    assert response.status_code == 500
    assert data["status_code"] == 500
    assert data["error"] == "Internal Server Error"
    assert data["message"] == "Unexpected server error"
