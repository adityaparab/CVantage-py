from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from typing import Any

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from mongomock_motor import AsyncMongoMockClient

from app.config import get_settings
from app.main import create_app


@pytest.fixture
def app_factory() -> Callable[[], FastAPI]:
    def _factory() -> FastAPI:
        get_settings.cache_clear()
        return create_app()

    return _factory


@pytest.fixture
def app_instance(app_factory: Callable[[], FastAPI]) -> FastAPI:
    return app_factory()


@pytest_asyncio.fixture
async def async_client(app_instance: FastAPI) -> AsyncIterator[AsyncClient]:
    async with AsyncClient(
        transport=ASGITransport(app=app_instance),
        base_url="http://test",
    ) as client:
        yield client


@pytest.fixture
def mongo_client() -> Any:
    return AsyncMongoMockClient()
