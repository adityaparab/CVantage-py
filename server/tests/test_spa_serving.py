"""Tests for single-server SPA serving (issue #92)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.config import Settings
from app.main import create_app
from app.spa import mount_spa


def _build_dist(tmp_path: Path) -> Path:
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<!doctype html><div id='root'></div>", encoding="utf-8")
    (dist / "assets" / "app-abc123.js").write_text("console.log(1)", encoding="utf-8")
    return dist


@pytest_asyncio.fixture
async def spa_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[AsyncClient]:
    dist = _build_dist(tmp_path)
    settings = Settings(environment="test", serve_spa=True, spa_dist_dir=str(dist))
    monkeypatch.setattr("app.main.get_settings", lambda: settings)
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client


@pytest.mark.asyncio
async def test_serves_index_at_root(spa_client: AsyncClient) -> None:
    resp = await spa_client.get("/")
    assert resp.status_code == 200
    assert "id='root'" in resp.text
    assert resp.headers["cache-control"] == "no-cache"


@pytest.mark.asyncio
async def test_deep_link_serves_spa(spa_client: AsyncClient) -> None:
    resp = await spa_client.get("/resumes/abc123")
    assert resp.status_code == 200
    assert "id='root'" in resp.text


@pytest.mark.asyncio
async def test_hashed_asset_is_immutable_cached(spa_client: AsyncClient) -> None:
    resp = await spa_client.get("/assets/app-abc123.js")
    assert resp.status_code == 200
    assert "immutable" in resp.headers["cache-control"]


@pytest.mark.asyncio
async def test_unknown_api_path_is_json_404(spa_client: AsyncClient) -> None:
    resp = await spa_client.get("/api/v1/does-not-exist")
    assert resp.status_code == 404
    assert resp.headers["content-type"].startswith("application/json")
    assert "id='root'" not in resp.text


def test_mount_spa_skips_when_dist_missing(tmp_path: Path) -> None:
    app = FastAPI()
    assert mount_spa(app, tmp_path / "nope") is False
