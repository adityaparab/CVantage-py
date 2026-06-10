from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

JobDrainHook = Callable[[float], Awaitable[None]]


async def noop_job_drain(_: float) -> None:
    return None


class ShutdownCoordinator:
    """Tracks in-flight requests and coordinates graceful shutdown drain."""

    def __init__(self) -> None:
        self._accepting_requests = True
        self._in_flight_requests = 0
        self._lock = asyncio.Lock()
        self._drained = asyncio.Event()
        self._drained.set()

    async def try_start_request(self) -> bool:
        async with self._lock:
            if not self._accepting_requests:
                return False

            self._in_flight_requests += 1
            self._drained.clear()
            return True

    async def finish_request(self) -> None:
        async with self._lock:
            if self._in_flight_requests > 0:
                self._in_flight_requests -= 1

            if not self._accepting_requests and self._in_flight_requests == 0:
                self._drained.set()

    async def begin_shutdown(self) -> None:
        async with self._lock:
            self._accepting_requests = False
            if self._in_flight_requests == 0:
                self._drained.set()

    async def wait_for_drain(self, timeout_seconds: float) -> bool:
        if timeout_seconds <= 0:
            return self._drained.is_set()

        try:
            await asyncio.wait_for(self._drained.wait(), timeout=timeout_seconds)
        except TimeoutError:
            return False
        return True

    @property
    def accepting_requests(self) -> bool:
        return self._accepting_requests
