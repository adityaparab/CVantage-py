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

import structlog
from pydantic import BaseModel
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)

from app.ai.models import AiModelService
from app.database.models import AiModelUsage

logger = structlog.get_logger("app.ai.llm")

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


def _extract_usage(raw: Any, model: str, duration_ms: int) -> LlmUsage:
    """Pull token counts off a LangChain AIMessage's usage_metadata."""
    usage = LlmUsage(model=model, duration_ms=duration_ms)
    meta = getattr(raw, "usage_metadata", None)
    if isinstance(meta, dict):
        usage.prompt_tokens = int(meta.get("input_tokens", 0) or 0)
        usage.completion_tokens = int(meta.get("output_tokens", 0) or 0)
        usage.total_tokens = int(
            meta.get("total_tokens", usage.prompt_tokens + usage.completion_tokens) or 0
        )
    return usage


class OpenAiLlmProvider(LlmProvider):
    """Real OpenAI provider using langchain-openai's ChatOpenAI.

    Captures per-call token usage, bounds output via ``max_tokens``, and attaches
    any configured observability callbacks (issue #54).
    """

    def __init__(
        self,
        model_service: AiModelService,
        usage: AiModelUsage,
        settings: Any = None,
    ) -> None:
        self._model_service = model_service
        self._usage = usage
        if settings is None:
            from app.config import get_settings

            settings = get_settings()
        self._settings = settings

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
        from pydantic import SecretStr

        from app.ai.observability import build_llm_callbacks

        # Resolve model + key
        resolved = await self._model_service.resolve_key(self._usage)
        if resolved is None:
            raise LlmQuotaError()
        _provider_name, resolved_model, api_key = resolved
        actual_model = model_name or resolved_model

        llm = ChatOpenAI(
            model=actual_model,
            api_key=SecretStr(api_key),
            temperature=temperature,
            timeout=self._settings.llm_timeout_seconds,
            max_tokens=self._settings.llm_max_output_tokens,  # type: ignore[call-arg]
            max_retries=0,  # We handle retries ourselves via tenacity
        )
        callbacks = build_llm_callbacks(self._settings)

        start = time.monotonic()
        try:
            structured_llm = llm.with_structured_output(
                schema, method="json_mode", include_raw=True
            )
            result = await structured_llm.ainvoke(
                [("system", system_prompt), ("human", user_prompt)],
                config={"callbacks": callbacks} if callbacks else None,
            )
        except Exception as e:
            err_str = str(e).lower()
            if "timeout" in err_str or "timed out" in err_str:
                raise LlmTimeoutError() from e
            if "quota" in err_str or "rate limit" in err_str or "insufficient" in err_str:
                raise LlmQuotaError() from e
            raise LlmInvalidOutputError(str(e)) from e

        duration_ms = int((time.monotonic() - start) * 1000)

        # include_raw=True yields {"raw": AIMessage, "parsed": <model|None>, "parsing_error": ...}
        raw = result.get("raw") if isinstance(result, dict) else None
        parsed_obj = result.get("parsed") if isinstance(result, dict) else result
        parsing_error = result.get("parsing_error") if isinstance(result, dict) else None
        if parsing_error is not None:
            raise LlmInvalidOutputError(str(parsing_error))

        if isinstance(parsed_obj, BaseModel):
            parsed = parsed_obj
        elif isinstance(parsed_obj, dict):
            try:
                parsed = schema.model_validate(parsed_obj)
            except Exception as e:
                raise LlmInvalidOutputError(str(e)) from e
        else:
            raise LlmInvalidOutputError(f"Unexpected output type: {type(parsed_obj)}")

        usage = _extract_usage(raw, actual_model, duration_ms)
        logger.info(
            "llm.call_completed",
            model=actual_model,
            usage_type=self._usage.value,
            duration_ms=duration_ms,
            prompt_tokens=usage.prompt_tokens,
            completion_tokens=usage.completion_tokens,
            total_tokens=usage.total_tokens,
        )
        return LlmResponse(parsed=parsed, usage=usage)


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
