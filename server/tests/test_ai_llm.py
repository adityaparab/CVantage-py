"""Tests for LlmService and FakeLlmProvider (issue #48)."""

from __future__ import annotations

import pytest
from pydantic import BaseModel, Field

from app.ai.llm import (
    FakeLlmProvider,
    LlmInvalidOutputError,
    LlmResponse,
)


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
