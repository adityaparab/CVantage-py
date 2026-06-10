from __future__ import annotations

import asyncio
import importlib
from typing import Any, cast

from fastapi import APIRouter

main_module = cast(Any, importlib.import_module("app.main"))


async def _init_database_stub(_: Any) -> None:
    return None


async def _close_database_stub() -> None:
    return None


main_module.init_database = cast(Any, _init_database_stub)
main_module.close_database = cast(Any, _close_database_stub)

app = main_module.create_app()

router = APIRouter(prefix="/test", tags=["test"])


@router.get("/slow")
async def slow(delay_ms: int = 700) -> dict[str, str]:
    await asyncio.sleep(delay_ms / 1000)
    return {"status": "ok"}


app.include_router(router, prefix="/api/v1")
