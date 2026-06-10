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


def _patch_mongomock_compat() -> None:
    """Make mongomock tolerate kwargs newer Beanie/pymongo pass.

    Beanie 1.29 calls ``list_collection_names(authorizedCollections=True,
    nameOnly=True)`` which mongomock's signature does not accept. Wrap it so
    the unsupported keyword arguments are dropped.
    """
    import mongomock.database

    db_cls = mongomock.database.Database
    if getattr(db_cls.list_collection_names, "_cvantage_patched", False):
        return

    original = db_cls.list_collection_names

    def _list_collection_names(self: Any, filter: Any = None, session: Any = None, **_: Any) -> Any:
        return original(self, filter=filter, session=session)  # type: ignore[no-untyped-call]

    _list_collection_names._cvantage_patched = True  # type: ignore[attr-defined]
    db_cls.list_collection_names = _list_collection_names  # type: ignore[method-assign]


@pytest_asyncio.fixture
async def beanie_db() -> AsyncIterator[Any]:
    """Initialise Beanie against an in-memory mongomock client.

    Yields a fresh client with empty collections per test so service-layer
    code can be exercised against real Beanie documents without a live Mongo.
    """
    from beanie import init_beanie

    from app.database.models import DOCUMENT_MODELS

    _patch_mongomock_compat()
    client: Any = AsyncMongoMockClient()
    await init_beanie(database=client["cvantage_test"], document_models=DOCUMENT_MODELS)
    await _drop_partial_unique_indexes(DOCUMENT_MODELS)
    yield client


async def _drop_partial_unique_indexes(models: list[Any]) -> None:
    """Drop unique indexes that carry a partialFilterExpression.

    mongomock silently ignores ``partialFilterExpression``, turning a partial
    unique index (e.g. "one active notification per analysis") into a global
    unique constraint and raising false DuplicateKeyErrors. Real Mongo enforces
    the partial condition correctly, so we simply drop these in tests.
    """
    for model in models:
        settings = getattr(model, "Settings", None)
        for index in getattr(settings, "indexes", None) or []:
            doc = getattr(index, "document", {})
            if doc.get("unique") and doc.get("partialFilterExpression") is not None:
                try:
                    await model.get_pymongo_collection().drop_index(doc["name"])
                except Exception:  # pragma: no cover - index may be absent
                    pass
