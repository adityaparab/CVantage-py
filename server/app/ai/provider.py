"""LLM provider resolution.

A single factory that picks the right :class:`LlmProvider` for a usage:
the real OpenAI provider when an active admin model or the env ``OPENAI_API_KEY``
is configured (and a master encryption key is present), otherwise the
deterministic fake provider — so the app runs fully offline and in tests.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from app.ai.llm import FakeLlmProvider, LlmProvider, OpenAiLlmProvider
from app.ai.models import AiModelService
from app.database.models import AiModelUsage

if TYPE_CHECKING:
    from app.config import Settings

_logger = structlog.get_logger("app.ai.provider")


async def get_llm_provider(usage: AiModelUsage, settings: Settings | None = None) -> LlmProvider:
    """Return the LLM provider to use for ``usage``.

    Resolution: active DB model → env ``OPENAI_API_KEY`` (both via the real
    provider) → deterministic fake. Requires ``MASTER_ENCRYPTION_KEY`` to use
    the real provider, since stored model keys are encrypted at rest.
    """
    if settings is None:
        from app.config import get_settings

        settings = get_settings()

    if not settings.master_encryption_key:
        return FakeLlmProvider()

    try:
        from app.ai.crypto import CryptoService

        model_service = AiModelService(CryptoService(settings.master_encryption_key), settings)
        if await model_service.resolve_key(usage) is not None:
            return OpenAiLlmProvider(model_service, usage, settings)
    except Exception as exc:  # noqa: BLE001 - never let resolution break the request
        _logger.warning("llm_provider.resolution_failed", usage=usage.value, error=str(exc))

    return FakeLlmProvider()
