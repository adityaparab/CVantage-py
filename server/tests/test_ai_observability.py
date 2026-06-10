"""Tests for env-gated LLM observability wiring (issue #54).

Verifies zero overhead when unconfigured and correct LangSmith env passthrough
when enabled.
"""

from __future__ import annotations

import os

import pytest

from app.ai.observability import build_llm_callbacks, configure_langsmith
from app.config import Settings


def _isolate_env(monkeypatch: pytest.MonkeyPatch) -> None:
    # Give configure_langsmith a scratch environ so writes don't leak.
    monkeypatch.setattr(os, "environ", {})


def test_langsmith_disabled_is_noop(monkeypatch: pytest.MonkeyPatch) -> None:
    _isolate_env(monkeypatch)
    settings = Settings(environment="test", langsmith_tracing=False)
    assert configure_langsmith(settings) is False
    assert "LANGSMITH_API_KEY" not in os.environ


def test_langsmith_enabled_without_key_is_noop(monkeypatch: pytest.MonkeyPatch) -> None:
    _isolate_env(monkeypatch)
    settings = Settings(environment="test", langsmith_tracing=True, langsmith_api_key=None)
    assert configure_langsmith(settings) is False
    assert "LANGSMITH_API_KEY" not in os.environ


def test_langsmith_enabled_exports_env(monkeypatch: pytest.MonkeyPatch) -> None:
    _isolate_env(monkeypatch)
    settings = Settings(
        environment="test",
        langsmith_tracing=True,
        langsmith_api_key="ls-secret",
        langsmith_project="cvantage",
    )
    assert configure_langsmith(settings) is True
    assert os.environ["LANGSMITH_TRACING"] == "true"
    assert os.environ["LANGSMITH_API_KEY"] == "ls-secret"
    assert os.environ["LANGSMITH_PROJECT"] == "cvantage"


def test_callbacks_empty_when_unconfigured() -> None:
    settings = Settings(environment="test")
    assert build_llm_callbacks(settings) == []


def test_callbacks_empty_when_langfuse_not_installed() -> None:
    # langfuse is not a project dependency, so even with keys set the import
    # guard yields no callbacks (zero overhead).
    settings = Settings(
        environment="test",
        langfuse_public_key="pk",
        langfuse_secret_key="sk",
    )
    assert build_llm_callbacks(settings) == []
