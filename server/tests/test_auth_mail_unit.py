from __future__ import annotations

from typing import Any

import pytest

import app.auth.mail as mail
from app.auth.mail import MailMessage
from app.config import Settings


@pytest.mark.asyncio
async def test_console_mail_service_logs_message(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    class _Logger:
        def info(self, event: str, **kwargs: Any) -> None:
            captured["event"] = event
            captured.update(kwargs)

    monkeypatch.setattr(mail, "logger", _Logger())

    service = mail.ConsoleMailService()
    await service.send(
        MailMessage(
            to_email="candidate@example.com",
            subject="Subject",
            text_body="Body",
        )
    )

    assert captured["event"] == "mail.console"
    assert captured["to_email"] == "candidate@example.com"
    assert captured["subject"] == "Subject"
    assert captured["body"] == "Body"


@pytest.mark.asyncio
async def test_smtp_mail_service_requires_host() -> None:
    service = mail.SmtpMailService(Settings(environment="test", mail_driver="smtp", smtp_host=None))

    with pytest.raises(RuntimeError):
        await service.send(
            MailMessage(
                to_email="candidate@example.com",
                subject="Subject",
                text_body="Body",
            )
        )


@pytest.mark.asyncio
async def test_smtp_mail_service_sends_with_composed_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    async def _fake_send(content: str, **kwargs: Any) -> None:
        captured["content"] = content
        captured.update(kwargs)

    monkeypatch.setattr("app.auth.mail.aiosmtplib.send", _fake_send)

    settings = Settings(
        environment="test",
        mail_driver="smtp",
        smtp_host="smtp.example.com",
        smtp_port=2525,
        smtp_user="smtp-user",
        smtp_password="smtp-pass",
        smtp_from="noreply@example.com",
    )
    service = mail.SmtpMailService(settings)

    await service.send(
        MailMessage(
            to_email="candidate@example.com",
            subject="Reset",
            text_body="Token",
        )
    )

    assert "From: noreply@example.com" in captured["content"]
    assert "To: candidate@example.com" in captured["content"]
    assert captured["hostname"] == "smtp.example.com"
    assert captured["port"] == 2525


def test_build_mail_service_switches_by_driver() -> None:
    assert isinstance(
        mail.build_mail_service(Settings(environment="test", mail_driver="console")),
        mail.ConsoleMailService,
    )
    assert isinstance(
        mail.build_mail_service(
            Settings(environment="test", mail_driver="smtp", smtp_host="smtp.example.com")
        ),
        mail.SmtpMailService,
    )
