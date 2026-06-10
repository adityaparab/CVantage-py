from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException

from app.config import Settings


@dataclass(slots=True)
class _AttemptState:
    failures: int = 0
    lockouts: int = 0
    locked_until: datetime | None = None


_state_by_key: dict[str, _AttemptState] = {}


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _key(email: str, ip: str | None) -> str:
    return f"{email.lower().strip()}|{ip or 'unknown'}"


def clear_abuse_state() -> None:
    _state_by_key.clear()


def ensure_not_locked(email: str, ip: str | None) -> None:
    state = _state_by_key.get(_key(email, ip))
    if state is None or state.locked_until is None:
        return

    if state.locked_until <= _utcnow():
        state.locked_until = None
        return

    raise HTTPException(status_code=429, detail={"message": "Account temporarily locked"})


def register_failure(email: str, ip: str | None, settings: Settings) -> timedelta | None:
    key = _key(email, ip)
    state = _state_by_key.setdefault(key, _AttemptState())
    now = _utcnow()

    if state.locked_until is not None and state.locked_until > now:
        raise HTTPException(status_code=429, detail={"message": "Account temporarily locked"})

    if state.locked_until is not None and state.locked_until <= now:
        state.locked_until = None

    state.failures += 1
    if state.failures < settings.auth_lockout_failure_threshold:
        return None

    state.failures = 0
    state.lockouts += 1
    duration_seconds = min(
        settings.auth_lockout_backoff_base_seconds * (2 ** (state.lockouts - 1)),
        settings.auth_lockout_backoff_max_seconds,
    )
    lockout_window = timedelta(seconds=duration_seconds)
    state.locked_until = now + lockout_window
    return lockout_window


def register_success(email: str, ip: str | None) -> None:
    state = _state_by_key.get(_key(email, ip))
    if state is None:
        return
    state.failures = 0
    state.locked_until = None
