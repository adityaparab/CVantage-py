"""SSE event streams for analysis progress (issue #57)."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from datetime import UTC, datetime

import structlog
from beanie import PydanticObjectId
from fastapi import HTTPException
from sse_starlette.sse import EventSourceResponse

from app.database.models import Analysis, AnalysisStatus

logger = structlog.get_logger("app.analyses.events")

# Per-user connection tracking for rate limiting
_active_connections: dict[str, int] = {}
MAX_CONNECTIONS_PER_USER = 5
HEARTBEAT_INTERVAL = 15


def _utcnow() -> datetime:
    return datetime.now(UTC)


async def _analysis_event_generator(
    analysis_id: PydanticObjectId,
    user_id_str: str,
) -> AsyncIterator[dict[str, object]]:
    """Generate SSE events for analysis progress.

    Sends current state immediately (for reconnect), then polls for changes.
    """
    # Send current state snapshot
    analysis = await Analysis.get(analysis_id)
    if analysis is not None:
        yield {
            "event": "snapshot",
            "data": json.dumps(
                {
                    "status": analysis.status.value,
                    "steps": [
                        {
                            "key": s.key.value,
                            "status": s.status.value,
                            "error": s.error,
                        }
                        for s in analysis.steps
                    ],
                    "timestamp": _utcnow().isoformat(),
                }
            ),
        }

    # Poll for status changes
    last_status = analysis.status.value if analysis else None
    while True:
        await asyncio.sleep(2)
        current = await Analysis.get(analysis_id)
        if current is None:
            yield {"event": "error", "data": json.dumps({"message": "Analysis not found"})}
            break

        if current.status.value != last_status:
            last_status = current.status.value
            yield {
                "event": "status_change",
                "data": json.dumps(
                    {
                        "status": current.status.value,
                        "steps": [
                            {
                                "key": s.key.value,
                                "status": s.status.value,
                                "error": s.error,
                            }
                            for s in current.steps
                        ],
                        "timestamp": _utcnow().isoformat(),
                    }
                ),
            }

            if current.status in (
                AnalysisStatus.COMPLETED,
                AnalysisStatus.FAILED,
                AnalysisStatus.CANCELLED,
            ):
                yield {"event": "done", "data": json.dumps({"status": current.status.value})}
                break


async def stream_analysis_events(
    analysis_id: PydanticObjectId,
    user_id: PydanticObjectId,
) -> EventSourceResponse:
    """Create an SSE response for analysis progress events."""
    # Ownership check
    analysis = await Analysis.find_one({"_id": analysis_id, "user_id": user_id, "deleted_at": None})
    if analysis is None:
        raise HTTPException(status_code=404, detail={"message": "Analysis not found"})

    user_key = str(user_id)
    conn_count = _active_connections.get(user_key, 0)
    if conn_count >= MAX_CONNECTIONS_PER_USER:
        raise HTTPException(status_code=429, detail={"message": "Too many SSE connections"})
    _active_connections[user_key] = conn_count + 1

    return EventSourceResponse(
        _analysis_event_generator(analysis_id, user_key),
        headers={
            "X-Accel-Buffering": "no",
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
        ping=HEARTBEAT_INTERVAL,
    )
