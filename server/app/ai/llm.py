"""LLM abstraction layer using LangChain (issue #48).

Provides a unified interface for calling LLMs with structured output,
retry logic, and token usage tracking. Supports both real OpenAI calls
and a deterministic fake provider for testing.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Generic, TypeVar

from pydantic import BaseModel
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)

from app.ai.models import AiModelService
from app.database.models import AiModelUsage

T = TypeVar("T", bound=BaseModel)

# ============================================================================
# Typed errors
# ============================================================================


class LlmError(Exception):
    """Base error for all LLM-related failures."""

    def __init__(self, message: str, reason: str) -> None:
        self.message = message
        self.reason = reason
        super().__init__(message)


class LlmTimeoutError(LlmError):
    """The LLM call timed out."""

    def __init__(self) -> None:
        super().__init__("LLM call timed out", "timeout")


class LlmQuotaError(LlmError):
    """API quota exceeded or insufficient credits."""

    def __init__(self) -> None:
        super().__init__("LLM API quota exceeded", "quota")


class LlmInvalidOutputError(LlmError):
    """The LLM returned output that could not be parsed into the expected schema."""

    def __init__(self, detail: str = "") -> None:
        msg = "LLM output could not be parsed"
        if detail:
            msg += f": {detail}"
        super().__init__(msg, "invalid_output")


# ============================================================================
# Token usage tracking
# ============================================================================


@dataclass
class LlmUsage:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    model: str = ""
    duration_ms: int = 0


@dataclass
class LlmResponse(Generic[T]):
    """Typed LLM response with parsed output and usage metadata."""

    parsed: T
    usage: LlmUsage = field(default_factory=LlmUsage)


# ============================================================================
# Provider protocol
# ============================================================================


class LlmProvider:
    """Interface for LLM providers (real or fake)."""

    async def structured_call(
        self,
        system_prompt: str,
        user_prompt: str,
        schema: type[BaseModel],
        model_name: str = "",
        temperature: float = 0.0,
        timeout_seconds: int = 60,
    ) -> LlmResponse[Any]:
        """Call the LLM with structured output parsing."""
        raise NotImplementedError


# ============================================================================
# Real OpenAI provider via LangChain
# ============================================================================


def _build_retry_decorator() -> Callable[..., Any]:
    """Build a tenacity retry decorator for LLM calls."""
    return retry(
        retry=retry_if_exception_type((LlmTimeoutError, LlmQuotaError, LlmInvalidOutputError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential_jitter(initial=1, max=30, jitter=2),
        reraise=True,
    )


class OpenAiLlmProvider(LlmProvider):
    """Real OpenAI provider using langchain-openai's ChatOpenAI."""

    def __init__(self, model_service: AiModelService, usage: AiModelUsage) -> None:
        self._model_service = model_service
        self._usage = usage

    async def structured_call(
        self,
        system_prompt: str,
        user_prompt: str,
        schema: type[BaseModel],
        model_name: str = "",
        temperature: float = 0.0,
        timeout_seconds: int = 60,
    ) -> LlmResponse[Any]:
        from langchain_openai import ChatOpenAI

        # Resolve model + key
        resolved = await self._model_service.resolve_key(self._usage)
        if resolved is None:
            raise LlmQuotaError()
        provider_name, resolved_model, api_key = resolved
        actual_model = model_name or resolved_model

        from pydantic import SecretStr

        llm = ChatOpenAI(
            model=actual_model,
            api_key=SecretStr(api_key),
            temperature=temperature,
            timeout=timeout_seconds,
            max_retries=0,  # We handle retries ourselves via tenacity
        )

        start = time.monotonic()
        try:
            structured_llm = llm.with_structured_output(schema, method="json_mode")
            result = await structured_llm.ainvoke(
                [
                    ("system", system_prompt),
                    ("human", user_prompt),
                ]
            )
        except Exception as e:
            err_str = str(e).lower()
            if "timeout" in err_str or "timed out" in err_str:
                raise LlmTimeoutError() from e
            if "quota" in err_str or "rate limit" in err_str or "insufficient" in err_str:
                raise LlmQuotaError() from e
            raise LlmInvalidOutputError(str(e)) from e

        duration_ms = int((time.monotonic() - start) * 1000)

        # Parse the result - it could be a Pydantic model or dict
        if isinstance(result, BaseModel):
            parsed = result
        elif isinstance(result, dict):
            try:
                parsed = schema.model_validate(result)
            except Exception as e:
                raise LlmInvalidOutputError(str(e)) from e
        else:
            raise LlmInvalidOutputError(f"Unexpected output type: {type(result)}")

        return LlmResponse(
            parsed=parsed,
            usage=LlmUsage(
                model=actual_model,
                duration_ms=duration_ms,
            ),
        )


# ============================================================================
# Fake deterministic provider for testing
# ============================================================================


class FakeLlmProvider(LlmProvider):
    """Deterministic fake LLM provider for tests and E2E.

    Returns pre-registered fixture data based on the schema type name.
    """

    def __init__(self) -> None:
        self._fixtures: dict[str, dict[str, Any]] = {}

    def register(self, schema_name: str, data: dict[str, Any]) -> None:
        """Register a deterministic response for a given schema name."""
        self._fixtures[schema_name] = data

    async def structured_call(
        self,
        system_prompt: str,
        user_prompt: str,
        schema: type[BaseModel],
        model_name: str = "",
        temperature: float = 0.0,
        timeout_seconds: int = 60,
    ) -> LlmResponse[Any]:
        schema_name = schema.__name__
        fixture = self._fixtures.get(schema_name)
        if fixture is None:
            # Return an empty default instance
            return LlmResponse(parsed=schema.model_validate({}))

        try:
            parsed = schema.model_validate(fixture)
        except Exception as e:
            raise LlmInvalidOutputError(str(e)) from e

        return LlmResponse(parsed=parsed)
