"""Tests for env-gated OpenTelemetry tracing (issue #96)."""

from __future__ import annotations

from typing import Any

import pytest
from fastapi import FastAPI

from app.config import Settings
from app.observability.otel import configure_otel


def test_disabled_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

    called = False

    def _fake_instrument(_app: FastAPI, **_kwargs: Any) -> None:
        nonlocal called
        called = True

    monkeypatch.setattr(FastAPIInstrumentor, "instrument_app", staticmethod(_fake_instrument))
    settings = Settings(environment="test", otel_enabled=False)
    assert configure_otel(FastAPI(), settings) is False
    assert called is False


def test_enabled_requires_endpoint() -> None:
    settings = Settings(environment="test", otel_enabled=True, otel_exporter_otlp_endpoint=None)
    assert configure_otel(FastAPI(), settings) is False


def test_enabled_instruments_app(monkeypatch: pytest.MonkeyPatch) -> None:
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

    captured: dict[str, Any] = {}

    def _fake_instrument(app: FastAPI, **kwargs: Any) -> None:
        captured["app"] = app
        captured["kwargs"] = kwargs

    monkeypatch.setattr(FastAPIInstrumentor, "instrument_app", staticmethod(_fake_instrument))
    app = FastAPI()
    settings = Settings(
        environment="test",
        otel_enabled=True,
        otel_exporter_otlp_endpoint="http://localhost:4318/v1/traces",
        otel_service_name="cvantage-test",
    )
    assert configure_otel(app, settings) is True
    assert captured["app"] is app
    assert "excluded_urls" in captured["kwargs"]
