from __future__ import annotations

from typing import Any

from beanie import init_beanie
from pymongo import AsyncMongoClient

from app.config import Settings
from app.database.models import DOCUMENT_MODELS

_client: AsyncMongoClient[Any] | None = None


async def init_database(settings: Settings) -> AsyncMongoClient[Any]:
    global _client
    _client = AsyncMongoClient(settings.mongodb_uri)
    db = _client.get_default_database(default=settings.mongodb_db_name)
    await init_beanie(database=db, document_models=DOCUMENT_MODELS)
    return _client


async def close_database() -> None:
    global _client
    if _client is not None:
        await _client.close()
        _client = None
