from __future__ import annotations

import pytest
from httpx import AsyncClient

from tests.factories import build_analysis_payload, build_resume_payload, build_user_payload


@pytest.mark.unit
def test_factory_helpers_build_expected_shapes() -> None:
    user = build_user_payload()
    resume = build_resume_payload()
    analysis = build_analysis_payload()

    assert user["email"].endswith("@example.com")
    assert "json_resume" in resume
    assert analysis["status"] == "pending"


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_async_client_fixture_hits_liveness(async_client: AsyncClient) -> None:
    response = await async_client.get("/api/v1/health/live")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
