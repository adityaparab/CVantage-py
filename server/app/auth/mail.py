from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import aiosmtplib
import structlog

from app.config import Settings

logger = structlog.get_logger(__name__)


@dataclass(slots=True)
class MailMessage:
    to_email: str
    subject: str
    text_body: str


class MailService(Protocol):
    async def send(self, message: MailMessage) -> None: ...


class ConsoleMailService:
    async def send(self, message: MailMessage) -> None:
        logger.info(
            "mail.console",
            to_email=message.to_email,
            subject=message.subject,
            body=message.text_body,
        )


class SmtpMailService:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def send(self, message: MailMessage) -> None:
        if not self._settings.smtp_host:
            raise RuntimeError("SMTP_HOST is required when MAIL_DRIVER=smtp")

        headers = {
            "From": self._settings.smtp_from,
            "To": message.to_email,
            "Subject": message.subject,
        }
        header_lines = [f"{key}: {value}" for key, value in headers.items()]
        content = "\r\n".join([*header_lines, "", message.text_body])

        await aiosmtplib.send(
            content,
            hostname=self._settings.smtp_host,
            port=self._settings.smtp_port,
            username=self._settings.smtp_user,
            password=self._settings.smtp_password,
        )


def build_mail_service(settings: Settings) -> MailService:
    if settings.mail_driver == "smtp":
        return SmtpMailService(settings)
    return ConsoleMailService()
