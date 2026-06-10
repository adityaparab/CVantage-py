import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


class _HealthyAdmin:
    async def command(self, _: str) -> dict[str, int]:
        return {"ok": 1}


class _HealthyClient:
    admin = _HealthyAdmin()


@pytest.mark.asyncio
async def test_health_ready_returns_200_when_all_checks_pass(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.health.router as health_router

    monkeypatch.setattr(health_router, "get_mongo_client", lambda: _HealthyClient())
    monkeypatch.setattr(health_router, "get_disk_free_mb", lambda: 500)
    monkeypatch.setattr(health_router, "get_memory_available_mb", lambda: 500)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/health/ready")

    data = response.json()
    assert response.status_code == 200
    assert data["status"] == "ready"
    assert data["checks"] == {"mongo": True, "disk": True, "memory": True}


@pytest.mark.asyncio
async def test_health_ready_returns_503_when_mongo_check_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.health.router as health_router

    monkeypatch.setattr(health_router, "get_mongo_client", lambda: None)
    monkeypatch.setattr(health_router, "get_disk_free_mb", lambda: 500)
    monkeypatch.setattr(health_router, "get_memory_available_mb", lambda: 500)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/health/ready")

    data = response.json()
    assert response.status_code == 503
    assert data["status_code"] == 503
    assert data["error"] == "Service Unavailable"
    assert data["details"]["checks"]["mongo"] is False
