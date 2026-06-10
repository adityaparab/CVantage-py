"""Tests for LlmService and FakeLlmProvider (issue #48)."""

from __future__ import annotations

from typing import Any

import langchain_openai
import pytest
from pydantic import BaseModel, Field

from app.ai.crypto import CryptoService
from app.ai.llm import (
    FakeLlmProvider,
    LlmInvalidOutputError,
    LlmProvider,
    LlmQuotaError,
    LlmResponse,
    LlmTimeoutError,
    OpenAiLlmProvider,
    _build_retry_decorator,
)
from app.ai.models import AiModelService
from app.config import Settings
from app.database.models import AiModelUsage

_TEST_MASTER_KEY = "MDEyMzQ1Njc4OWFiY2RlZjAxMjM0NTY3ODlhYmNkZWY="


class _TestSchema(BaseModel):
    """A simple test schema for fake provider tests."""

    name: str = Field(default="")
    score: int = Field(default=0, ge=0, le=100)


class _NestedSchema(BaseModel):
    """A nested schema."""

    items: list[str] = Field(default_factory=list)
    metadata: dict[str, str] = Field(default_factory=dict)


class TestFakeLlmProvider:
    @pytest.mark.asyncio
    async def test_returns_registered_fixture(self) -> None:
        provider = FakeLlmProvider()
        provider.register("_TestSchema", {"name": "Python Expert", "score": 95})

        response = await provider.structured_call(
            system_prompt="",
            user_prompt="",
            schema=_TestSchema,
        )
        assert isinstance(response, LlmResponse)
        parsed = response.parsed
        assert isinstance(parsed, _TestSchema)
        assert parsed.name == "Python Expert"
        assert parsed.score == 95

    @pytest.mark.asyncio
    async def test_returns_default_when_no_fixture(self) -> None:
        provider = FakeLlmProvider()
        response = await provider.structured_call(
            system_prompt="",
            user_prompt="",
            schema=_TestSchema,
        )
        parsed = response.parsed
        assert parsed.name == ""
        assert parsed.score == 0

    @pytest.mark.asyncio
    async def test_invalid_fixture_raises(self) -> None:
        provider = FakeLlmProvider()
        # Register data that doesn't match the schema
        provider.register("_TestSchema", {"name": 123, "score": "bad"})

        with pytest.raises(LlmInvalidOutputError):
            await provider.structured_call(
                system_prompt="",
                user_prompt="",
                schema=_TestSchema,
            )

    @pytest.mark.asyncio
    async def test_nested_schema(self) -> None:
        provider = FakeLlmProvider()
        data = {
            "items": ["a", "b", "c"],
            "metadata": {"key": "value"},
        }
        provider.register("_NestedSchema", data)

        response = await provider.structured_call(
            system_prompt="", user_prompt="", schema=_NestedSchema
        )
        parsed = response.parsed
        assert parsed.items == ["a", "b", "c"]
        assert parsed.metadata == {"key": "value"}

    @pytest.mark.asyncio
    async def test_deterministic(self) -> None:
        """Multiple calls with the same fixture return identical results."""
        provider = FakeLlmProvider()
        provider.register("_TestSchema", {"name": "Python Expert", "score": 95})

        r1 = await provider.structured_call("", "", _TestSchema)
        r2 = await provider.structured_call("", "", _TestSchema)
        assert r1.parsed.model_dump() == r2.parsed.model_dump()

    @pytest.mark.asyncio
    async def test_register_multiple_schemas(self) -> None:
        provider = FakeLlmProvider()
        provider.register("_TestSchema", {"name": "A", "score": 50})
        provider.register("_NestedSchema", {"items": ["x"]})

        r1 = await provider.structured_call("", "", _TestSchema)
        r2 = await provider.structured_call("", "", _NestedSchema)
        assert r1.parsed.name == "A"
        assert r2.parsed.items == ["x"]

    @pytest.mark.asyncio
    async def test_usage_tracking_returned(self) -> None:
        provider = FakeLlmProvider()
        provider.register("_TestSchema", {"name": "Test", "score": 80})
        response = await provider.structured_call("", "", _TestSchema)
        assert response.usage.prompt_tokens == 0
        assert response.usage.duration_ms == 0


def test_base_provider_is_abstract() -> None:
    import asyncio

    with pytest.raises(NotImplementedError):
        asyncio.run(LlmProvider().structured_call("", "", _TestSchema))


def test_retry_decorator_builds() -> None:
    decorator = _build_retry_decorator()
    assert callable(decorator)


class _RawMessage:
    def __init__(self, usage_metadata: dict[str, int] | None) -> None:
        self.usage_metadata = usage_metadata


class _FakeStructured:
    def __init__(self, outcome: Any, usage: dict[str, int] | None, parsing_error: Any) -> None:
        self._outcome = outcome
        self._usage = usage
        self._parsing_error = parsing_error

    async def ainvoke(self, _messages: Any, config: Any = None) -> Any:
        if isinstance(self._outcome, Exception):
            raise self._outcome
        return {
            "raw": _RawMessage(self._usage),
            "parsed": self._outcome,
            "parsing_error": self._parsing_error,
        }


class _FakeChatOpenAI:
    outcome: Any = None
    usage: dict[str, int] | None = None
    parsing_error: Any = None
    captured: dict[str, Any] = {}

    def __init__(self, **kwargs: Any) -> None:
        type(self).captured = kwargs

    def with_structured_output(
        self, schema: type[BaseModel], method: str = "json_mode", include_raw: bool = False
    ) -> Any:
        return _FakeStructured(type(self).outcome, type(self).usage, type(self).parsing_error)


def _model_service(*, openai_api_key: str | None = "env-key") -> AiModelService:
    settings = Settings(
        environment="test",
        master_encryption_key=_TEST_MASTER_KEY,
        openai_api_key=openai_api_key,
    )
    return AiModelService(CryptoService(settings.master_encryption_key), settings)


@pytest.mark.usefixtures("beanie_db")
class TestOpenAiLlmProvider:
    def setup_method(self) -> None:
        _FakeChatOpenAI.outcome = None
        _FakeChatOpenAI.usage = None
        _FakeChatOpenAI.parsing_error = None
        _FakeChatOpenAI.captured = {}

    @pytest.mark.asyncio
    async def test_no_key_raises_quota(self) -> None:
        provider = OpenAiLlmProvider(_model_service(openai_api_key=None), AiModelUsage.ANALYSIS)
        with pytest.raises(LlmQuotaError):
            await provider.structured_call("sys", "user", _TestSchema)

    @pytest.mark.asyncio
    async def test_success_captures_usage_and_bounds_tokens(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _FakeChatOpenAI.outcome = _TestSchema(name="Real", score=88)
        _FakeChatOpenAI.usage = {"input_tokens": 120, "output_tokens": 30, "total_tokens": 150}
        monkeypatch.setattr(langchain_openai, "ChatOpenAI", _FakeChatOpenAI)
        provider = OpenAiLlmProvider(_model_service(), AiModelUsage.ANALYSIS)
        response = await provider.structured_call("sys", "user", _TestSchema)
        assert response.parsed.name == "Real"
        assert response.usage.model == "gpt-4o"
        assert response.usage.prompt_tokens == 120
        assert response.usage.completion_tokens == 30
        assert response.usage.total_tokens == 150
        # Output is bounded by the configured max_tokens.
        assert _FakeChatOpenAI.captured["max_tokens"] == 2048

    @pytest.mark.asyncio
    async def test_parsing_error_is_invalid_output(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _FakeChatOpenAI.outcome = None
        _FakeChatOpenAI.parsing_error = ValueError("could not parse")
        monkeypatch.setattr(langchain_openai, "ChatOpenAI", _FakeChatOpenAI)
        provider = OpenAiLlmProvider(_model_service(), AiModelUsage.ANALYSIS)
        with pytest.raises(LlmInvalidOutputError):
            await provider.structured_call("sys", "user", _TestSchema)

    @pytest.mark.asyncio
    async def test_success_with_dict_result(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _FakeChatOpenAI.outcome = {"name": "FromDict", "score": 50}
        monkeypatch.setattr(langchain_openai, "ChatOpenAI", _FakeChatOpenAI)
        provider = OpenAiLlmProvider(_model_service(), AiModelUsage.ANALYSIS)
        response = await provider.structured_call("sys", "user", _TestSchema)
        assert response.parsed.name == "FromDict"

    @pytest.mark.asyncio
    async def test_timeout_mapped(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _FakeChatOpenAI.outcome = RuntimeError("Request timed out")
        monkeypatch.setattr(langchain_openai, "ChatOpenAI", _FakeChatOpenAI)
        provider = OpenAiLlmProvider(_model_service(), AiModelUsage.ANALYSIS)
        with pytest.raises(LlmTimeoutError):
            await provider.structured_call("sys", "user", _TestSchema)

    @pytest.mark.asyncio
    async def test_quota_mapped(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _FakeChatOpenAI.outcome = RuntimeError("insufficient quota / rate limit")
        monkeypatch.setattr(langchain_openai, "ChatOpenAI", _FakeChatOpenAI)
        provider = OpenAiLlmProvider(_model_service(), AiModelUsage.ANALYSIS)
        with pytest.raises(LlmQuotaError):
            await provider.structured_call("sys", "user", _TestSchema)

    @pytest.mark.asyncio
    async def test_invalid_output_mapped(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _FakeChatOpenAI.outcome = RuntimeError("garbled response")
        monkeypatch.setattr(langchain_openai, "ChatOpenAI", _FakeChatOpenAI)
        provider = OpenAiLlmProvider(_model_service(), AiModelUsage.ANALYSIS)
        with pytest.raises(LlmInvalidOutputError):
            await provider.structured_call("sys", "user", _TestSchema)

    @pytest.mark.asyncio
    async def test_unexpected_output_type_invalid(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _FakeChatOpenAI.outcome = 12345  # not a BaseModel or dict
        monkeypatch.setattr(langchain_openai, "ChatOpenAI", _FakeChatOpenAI)
        provider = OpenAiLlmProvider(_model_service(), AiModelUsage.ANALYSIS)
        with pytest.raises(LlmInvalidOutputError):
            await provider.structured_call("sys", "user", _TestSchema)
