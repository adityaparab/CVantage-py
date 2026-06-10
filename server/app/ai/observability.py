"""LLM observability wiring (issue #54).

Two env-gated integrations with **zero overhead when unconfigured**:

* LangSmith — LangChain reads ``LANGSMITH_*`` from the environment, so we
  passthrough the validated settings into ``os.environ`` once at boot.
* Langfuse — an optional callback handler attached per LLM call. The dependency
  is optional; if it is not installed or not configured, no callbacks are used.

This is the single module permitted to write the LangSmith passthrough vars to
``os.environ``; nothing reads provider config from the environment directly.
"""

from __future__ import annotations

import os
from typing import Any

import structlog

from app.config import Settings

logger = structlog.get_logger("app.ai.observability")

_langfuse_unavailable_logged = False


def configure_langsmith(settings: Settings) -> bool:
    """Export LangSmith env vars when tracing is enabled. Returns True if enabled.

    No-op (and no network calls) when ``langsmith_tracing`` is false or no API
    key is configured.
    """
    if not settings.langsmith_tracing or not settings.langsmith_api_key:
        return False

    os.environ["LANGSMITH_TRACING"] = "true"
    os.environ["LANGSMITH_API_KEY"] = settings.langsmith_api_key
    if settings.langsmith_project:
        os.environ["LANGSMITH_PROJECT"] = settings.langsmith_project
    if settings.langsmith_endpoint:
        os.environ["LANGSMITH_ENDPOINT"] = settings.langsmith_endpoint
    logger.info("observability.langsmith_enabled", project=settings.langsmith_project)
    return True


def build_llm_callbacks(settings: Settings) -> list[Any]:
    """Build per-call LLM callbacks (currently Langfuse, if configured).

    Returns an empty list when Langfuse is not configured or not installed, so
    callers can always pass ``config={"callbacks": build_llm_callbacks(...)}``.
    """
    global _langfuse_unavailable_logged

    if not (settings.langfuse_public_key and settings.langfuse_secret_key):
        return []

    try:
        from langfuse.callback import CallbackHandler  # type: ignore[import-not-found]
    except ImportError:
        if not _langfuse_unavailable_logged:
            logger.warning("observability.langfuse_not_installed")
            _langfuse_unavailable_logged = True
        return []

    handler = CallbackHandler(
        public_key=settings.langfuse_public_key,
        secret_key=settings.langfuse_secret_key,
        host=settings.langfuse_host or "https://cloud.langfuse.com",
    )
    return [handler]
