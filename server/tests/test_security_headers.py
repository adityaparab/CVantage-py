"""Tests for security headers and CSP hardening (issue #98)."""

from __future__ import annotations

import base64
import hashlib
import re
from collections.abc import Awaitable, Callable
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from app.config import Settings
from app.main import CONTENT_SECURITY_POLICY, INLINE_THEME_SCRIPT_HASH, create_app

ClientFactory = Callable[..., Awaitable[AsyncClient]]


@pytest.fixture
def client_factory(monkeypatch: pytest.MonkeyPatch) -> ClientFactory:
    async def _make(environment: str = "test") -> AsyncClient:
        settings = Settings(environment=environment)  # type: ignore[arg-type]
        monkeypatch.setattr("app.main.get_settings", lambda: settings)
        app = create_app()
        return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")

    return _make


@pytest.mark.asyncio
async def test_security_headers_on_responses(client_factory: ClientFactory) -> None:
    client = await client_factory()
    async with client:
        resp = await client.get("/api/v1/__no_such_route__")
    csp = resp.headers["content-security-policy"]
    assert "default-src 'self'" in csp
    assert "object-src 'none'" in csp
    assert "frame-ancestors 'none'" in csp
    assert "base-uri 'self'" in csp
    assert INLINE_THEME_SCRIPT_HASH in csp
    assert resp.headers["x-content-type-options"] == "nosniff"
    assert resp.headers["x-frame-options"] == "DENY"
    assert resp.headers["referrer-policy"] == "no-referrer"


@pytest.mark.asyncio
async def test_hsts_only_in_production(client_factory: ClientFactory) -> None:
    dev_client = await client_factory("development")
    async with dev_client:
        dev = await dev_client.get("/api/v1/__x__")
    assert "strict-transport-security" not in dev.headers

    prod_client = await client_factory("production")
    async with prod_client:
        prod = await prod_client.get("/api/v1/__x__")
    assert "max-age=31536000" in prod.headers["strict-transport-security"]


def test_inline_theme_script_hash_matches_index_html() -> None:
    """Guard against the CSP hash drifting from the actual inline script."""
    index_html = Path(__file__).resolve().parents[2] / "frontend" / "index.html"
    html = index_html.read_text(encoding="utf-8")
    match = re.search(r"<script>(.*?)</script>", html, re.S)
    assert match is not None
    digest = base64.b64encode(hashlib.sha256(match.group(1).encode("utf-8")).digest()).decode()
    assert INLINE_THEME_SCRIPT_HASH == f"sha256-{digest}"
    assert INLINE_THEME_SCRIPT_HASH in CONTENT_SECURITY_POLICY
