"""Tests for env-gated Sentry error tracking (issue #95)."""

from __future__ import annotations

from typing import Any

import pytest

from app.config import Settings
from app.observability.sentry import _before_send, _scrub, configure_sentry


class TestScrub:
    def test_redacts_sensitive_keys(self) -> None:
        event = {
            "json_resume": {"basics": {"name": "Ada"}},
            "password": "hunter2",
            "extra": {"api_key": "sk-secret", "ok": "keep"},
        }
        scrubbed = _scrub(event)
        assert scrubbed["json_resume"] == "[redacted]"
        assert scrubbed["password"] == "[redacted]"
        assert scrubbed["extra"]["api_key"] == "[redacted]"
        assert scrubbed["extra"]["ok"] == "keep"

    def test_scrubs_inside_lists(self) -> None:
        event = {"items": [{"original_text": "secret resume"}, {"ok": 1}]}
        scrubbed = _scrub(event)
        assert scrubbed["items"][0]["original_text"] == "[redacted]"
        assert scrubbed["items"][1]["ok"] == 1

    def test_before_send_scrubs(self) -> None:
        out = _before_send({"job_description": "long JD text"}, {})
        assert out["job_description"] == "[redacted]"


class TestConfigure:
    def test_disabled_without_dsn(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import sentry_sdk

        called = False

        def _fake_init(**_kwargs: Any) -> None:
            nonlocal called
            called = True

        monkeypatch.setattr(sentry_sdk, "init", _fake_init)
        settings = Settings(environment="test", sentry_dsn=None)
        assert configure_sentry(settings) is False
        assert called is False

    def test_enabled_with_dsn_scrubs(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import sentry_sdk

        captured: dict[str, Any] = {}

        def _fake_init(**kwargs: Any) -> None:
            captured.update(kwargs)

        monkeypatch.setattr(sentry_sdk, "init", _fake_init)
        settings = Settings(
            environment="production",
            sentry_dsn="https://abc@o1.ingest.sentry.io/1",
            sentry_traces_sample_rate=0.25,
        )
        assert configure_sentry(settings) is True
        assert captured["environment"] == "production"
        assert captured["traces_sample_rate"] == 0.25
        assert captured["send_default_pii"] is False
        # The before_send hook scrubs sensitive payloads.
        assert captured["before_send"]({"password": "x"}, {}) == {"password": "[redacted]"}
