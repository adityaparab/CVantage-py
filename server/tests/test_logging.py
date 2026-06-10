import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.observability.logging import redact_secrets


@pytest.mark.asyncio
async def test_request_id_header_is_echoed() -> None:
    request_id = "req-123"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/health/live", headers={"x-request-id": request_id})

    assert response.status_code == 200
    assert response.headers["x-request-id"] == request_id


def test_redact_secrets_processor_masks_sensitive_fields() -> None:
    event = {
        "headers": {
            "authorization": "Bearer abc",
            "x-request-id": "rid",
        },
        "token": "abc123",
        "password_hash": "secret",
        "nested": {"api_key": "k", "safe": "ok"},
    }

    redacted = redact_secrets(None, "info", event)

    assert redacted["headers"]["authorization"] == "[REDACTED]"
    assert redacted["headers"]["x-request-id"] == "rid"
    assert redacted["token"] == "[REDACTED]"
    assert redacted["password_hash"] == "[REDACTED]"
    assert redacted["nested"]["api_key"] == "[REDACTED]"
    assert redacted["nested"]["safe"] == "ok"
