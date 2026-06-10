"""Mongo-backed job runner (issue #50).

Provides a ``JobRunner`` Protocol and a ``MongoJobRunner`` implementation
that uses the ``analyses`` collection as its job queue.  Jobs are claimed
atomically via ``find_one_and_update``, tracked with heartbeats, and
recovered if a worker crashes.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from typing import Protocol, runtime_checkable

import structlog
from beanie import PydanticObjectId

from app.database.models import Analysis, AnalysisStatus

logger = structlog.get_logger("app.jobs")

MAX_RETRIES = 5
HEARTBEAT_INTERVAL_SECONDS = 15
STALE_HEARTBEAT_SECONDS = 60
DEFAULT_CONCURRENCY = 5

JobHandler = Callable[[Analysis], Awaitable[None]]


@runtime_checkable
class JobRunner(Protocol):
    """Interface for a background job runner."""

    async def start(self, handler: JobHandler) -> None: ...
    async def shutdown(self, timeout_seconds: float) -> None: ...
    async def recover_stale_jobs(self) -> int: ...


class MongoJobRunner:
    """Background worker that processes Analysis jobs from MongoDB.

    Uses a fixed-size pool of asyncio tasks to claim and process jobs
    from the ``analyses`` collection.
    """

    def __init__(
        self,
        concurrency: int = DEFAULT_CONCURRENCY,
        heartbeat_interval: float = HEARTBEAT_INTERVAL_SECONDS,
        stale_seconds: float = STALE_HEARTBEAT_SECONDS,
        max_retries: int = MAX_RETRIES,
    ) -> None:
        self._concurrency = concurrency
        self._heartbeat_interval = heartbeat_interval
        self._stale_seconds = stale_seconds
        self._max_retries = max_retries
        self._running = False
        self._tasks: list[asyncio.Task[None]] = []
        self._in_flight: set[asyncio.Task[None]] = set()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def start(self, handler: JobHandler) -> None:
        """Start *concurrency* worker tasks that poll for jobs."""
        self._running = True
        recovered = await self.recover_stale_jobs()
        if recovered:
            logger.info("job_runner.recovered_stale_jobs", count=recovered)

        for i in range(self._concurrency):
            task = asyncio.create_task(self._worker_loop(i, handler))
            self._tasks.append(task)

        logger.info(
            "job_runner.started",
            concurrency=self._concurrency,
            heartbeat_interval=self._heartbeat_interval,
        )

    async def shutdown(self, timeout_seconds: float = 30.0) -> None:
        """Signal workers to stop and wait for in-flight jobs to finish."""
        self._running = False
        if not self._tasks:
            return

        logger.info("job_runner.shutdown_starting", timeout=timeout_seconds)
        done, pending = await asyncio.wait(
            self._tasks, timeout=timeout_seconds, return_when=asyncio.ALL_COMPLETED
        )
        for task in pending:
            task.cancel()
        logger.info(
            "job_runner.shutdown_complete",
            completed=len(done),
            cancelled=len(pending),
        )

    async def recover_stale_jobs(self) -> int:
        """Re-queue jobs whose heartbeat is older than *stale_seconds*."""
        cutoff = _utcnow() - timedelta(seconds=self._stale_seconds)
        recovered = 0
        cursor = Analysis.find(
            {
                "status": AnalysisStatus.IN_PROGRESS.value,
                "heartbeat_at": {"$lt": cutoff},
            }
        )
        async for job in cursor:
            if job.retry_count >= self._max_retries:
                job.status = AnalysisStatus.FAILED
                job.error = "Max retries exceeded after stale heartbeat"
                await job.save()
                logger.warning("job_runner.marked_failed", job_id=str(job.id))
            else:
                job.status = AnalysisStatus.PENDING
                job.retry_count += 1
                job.heartbeat_at = None
                await job.save()
                recovered += 1
                logger.info(
                    "job_runner.recovered",
                    job_id=str(job.id),
                    retry=job.retry_count,
                )
        return recovered

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    async def _worker_loop(self, worker_id: int, handler: JobHandler) -> None:
        """Continuously claim and process jobs."""
        while self._running:
            try:
                job = await self._claim_job()
                if job is None:
                    await asyncio.sleep(1)
                    continue

                await self._process_job(job, handler, worker_id)
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("job_runner.worker_error", worker_id=worker_id)

    async def _claim_job(self) -> Analysis | None:
        """Atomically claim the next pending job."""
        now = _utcnow()
        job = await Analysis.find_one_and_update(
            {"status": AnalysisStatus.PENDING.value},
            {
                "$set": {
                    "status": AnalysisStatus.IN_PROGRESS.value,
                    "heartbeat_at": now,
                    "started_at": now,
                }
            },
            sort=[("created_at", 1)],
        )
        if job is not None:
            logger.info("job_runner.claimed", job_id=str(job.id))
        return job  # type: ignore[no-any-return]

    async def _process_job(self, job: Analysis, handler: JobHandler, worker_id: int) -> None:
        """Run the handler with heartbeat keep-alive."""
        assert job.id is not None, "Job must have an id"
        heartbeat_task = asyncio.create_task(self._heartbeat_loop(job.id))
        try:
            await handler(job)
            job.status = AnalysisStatus.COMPLETED
            job.completed_at = _utcnow()
            await job.save()
            logger.info("job_runner.completed", job_id=str(job.id))
        except Exception as e:
            logger.exception("job_runner.failed", job_id=str(job.id))
            if job.retry_count >= self._max_retries:
                job.status = AnalysisStatus.FAILED
                job.error = str(e)[:2000]
            else:
                job.status = AnalysisStatus.PENDING
                job.retry_count += 1
                job.error = str(e)[:2000]
            job.heartbeat_at = None
            await job.save()
        finally:
            heartbeat_task.cancel()
            try:
                await heartbeat_task
            except asyncio.CancelledError:
                pass

    async def _heartbeat_loop(self, job_id: PydanticObjectId) -> None:
        """Periodically update the job's heartbeat timestamp."""
        try:
            while self._running:
                await asyncio.sleep(self._heartbeat_interval)
                await Analysis.find({"_id": job_id}).update({"$set": {"heartbeat_at": _utcnow()}})
        except asyncio.CancelledError:
            pass


def _utcnow() -> datetime:
    return datetime.now(UTC)
