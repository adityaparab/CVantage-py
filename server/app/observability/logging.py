from __future__ import annotations

import logging
from typing import Any, cast

import structlog

SENSITIVE_KEY_PARTS = (
    "authorization",
    "cookie",
    "password",
    "secret",
    "token",
    "api_key",
    "apikey",
    "key",
)


def _is_sensitive_key(key: str) -> bool:
    normalized = key.lower()
    return any(part in normalized for part in SENSITIVE_KEY_PARTS)


def _redact_value(value: Any) -> Any:
    if isinstance(value, dict):
        redacted: dict[str, Any] = {}
        for key, inner in value.items():
            if _is_sensitive_key(key):
                redacted[key] = "[REDACTED]"
            else:
                redacted[key] = _redact_value(inner)
        return redacted

    if isinstance(value, list):
        return [_redact_value(item) for item in value]

    return value


def redact_secrets(
    _: structlog.typing.WrappedLogger,
    __: str,
    event_dict: structlog.typing.EventDict,
) -> structlog.typing.EventDict:
    return cast(structlog.typing.EventDict, _redact_value(event_dict))


def configure_logging(log_level: str, environment: str) -> None:
    renderer: structlog.typing.Processor
    if environment == "development":
        renderer = structlog.dev.ConsoleRenderer()
    else:
        renderer = structlog.processors.JSONRenderer()

    timestamper = structlog.processors.TimeStamper(fmt="iso", utc=True)

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.add_log_level,
            timestamper,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            redact_secrets,
            renderer,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    logging.basicConfig(
        level=getattr(logging, log_level.upper(), logging.INFO),
        format="%(message)s",
    )
