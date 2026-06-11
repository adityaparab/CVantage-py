"""Tests for the LLM provider factory (real-vs-fake resolution)."""

from __future__ import annotations

import base64

import pytest

from app.ai.llm import FakeLlmProvider, OpenAiLlmProvider
from app.ai.models import AiModelService
from app.ai.provider import get_llm_provider
from app.config import Settings
from app.database.models import AiModelUsage

# Valid 32-byte (AES-256) master key for the tests that exercise the real path.
ZERO_KEY = base64.b64encode(b"\x00" * 32).decode()


@pytest.mark.asyncio
async def test_falls_back_to_fake_without_master_key() -> None:
    settings = Settings(environment="test", master_encryption_key="")
    provider = await get_llm_provider(AiModelUsage.ANALYSIS, settings)
    assert isinstance(provider, FakeLlmProvider)


@pytest.mark.asyncio
async def test_uses_real_provider_when_a_model_resolves(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _resolve(self: AiModelService, usage: AiModelUsage) -> tuple[str, str, str]:
        return ("openai", "gpt-4o", "sk-test-key")

    monkeypatch.setattr(AiModelService, "resolve_key", _resolve)
    settings = Settings(environment="test", master_encryption_key=ZERO_KEY)
    provider = await get_llm_provider(AiModelUsage.ANALYSIS, settings)
    assert isinstance(provider, OpenAiLlmProvider)


@pytest.mark.asyncio
async def test_falls_back_to_fake_when_nothing_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _resolve(self: AiModelService, usage: AiModelUsage) -> None:
        return None

    monkeypatch.setattr(AiModelService, "resolve_key", _resolve)
    settings = Settings(environment="test", master_encryption_key=ZERO_KEY)
    provider = await get_llm_provider(AiModelUsage.RESUME_PARSING, settings)
    assert isinstance(provider, FakeLlmProvider)


@pytest.mark.asyncio
async def test_falls_back_to_fake_on_resolution_error(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _boom(self: AiModelService, usage: AiModelUsage) -> None:
        raise RuntimeError("db down")

    monkeypatch.setattr(AiModelService, "resolve_key", _boom)
    settings = Settings(environment="test", master_encryption_key=ZERO_KEY)
    provider = await get_llm_provider(AiModelUsage.ANALYSIS, settings)
    assert isinstance(provider, FakeLlmProvider)
