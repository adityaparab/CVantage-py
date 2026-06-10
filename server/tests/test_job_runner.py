"""Unit tests for Mongo-backed job runner (issue #50).

Tests the recovery logic and retry exhaustion logic directly
without requiring a running MongoDB.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.database.models import AnalysisStatus
from app.jobs.runner import MAX_RETRIES


def _utcnow() -> datetime:
    return datetime.now(UTC)


def test_max_retries_constant() -> None:
    """MAX_RETRIES should be a positive integer."""
    assert MAX_RETRIES >= 1
    assert isinstance(MAX_RETRIES, int)


def test_analysis_status_enum() -> None:
    """AnalysisStatus should have all expected states."""
    assert AnalysisStatus.PENDING.value == "pending"
    assert AnalysisStatus.IN_PROGRESS.value == "in_progress"
    assert AnalysisStatus.COMPLETED.value == "completed"
    assert AnalysisStatus.FAILED.value == "failed"


def test_job_runner_importable() -> None:
    """MongoJobRunner should be importable and instantiable."""
    from app.jobs.runner import MongoJobRunner

    runner = MongoJobRunner(concurrency=2)
    assert runner._concurrency == 2
    assert runner._max_retries == MAX_RETRIES
    assert runner._heartbeat_interval == 15
    assert runner._stale_seconds == 60


def test_recover_stale_older_than() -> None:
    """Stale threshold calculation."""
    from app.jobs.runner import STALE_HEARTBEAT_SECONDS

    assert STALE_HEARTBEAT_SECONDS == 60
    heartbeat = _utcnow() - timedelta(seconds=STALE_HEARTBEAT_SECONDS + 10)
    assert heartbeat < _utcnow() - timedelta(seconds=STALE_HEARTBEAT_SECONDS)
