"""Env-gated Sentry error tracking (issue #95).

Zero overhead unless ``SENTRY_DSN`` is configured. A ``before_send`` hook scrubs
known-sensitive payloads so resume/analysis **content** and secrets never leave
the process — only metadata and stack traces are reported.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.config import Settings

# Keys whose values must never reach Sentry (resume/analysis content + secrets).
_SCRUB_KEYS = frozenset(
    {
        "json_resume",
        "jsonresume",
        "original_text",
        "resume_text",
        "job_description",
        "password",
        "password_hash",
        "api_key",
        "api_key_encrypted",
        "token",
        "token_hash",
        "access_token",
        "refresh_token",
        "authorization",
    }
)
_REDACTED = "[redacted]"


def _scrub(value: Any) -> Any:
    """Recursively redact sensitive keys from a Sentry event payload."""
    if isinstance(value, dict):
        return {
            key: (_REDACTED if key.lower() in _SCRUB_KEYS else _scrub(val))
            for key, val in value.items()
        }
    if isinstance(value, list):
        return [_scrub(item) for item in value]
    return value


def _before_send(event: Any, _hint: Any) -> Any:
    # Typed as Any to match Sentry's Event TypedDict without a hard dependency on
    # its internal types; _scrub preserves the mapping shape.
    return _scrub(event)


def configure_sentry(settings: Settings) -> bool:
    """Initialise Sentry when a DSN is set. Returns whether it was enabled."""
    if not settings.sentry_dsn:
        return False

    import sentry_sdk

    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.environment,
        release=settings.sentry_release,
        traces_sample_rate=settings.sentry_traces_sample_rate,
        send_default_pii=False,
        before_send=_before_send,
    )
    return True
