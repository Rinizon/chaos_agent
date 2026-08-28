"""Structured logging with conservative secret sanitization."""

import json
import logging
import re
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from enum import StrEnum
from typing import TextIO

from chaos_agent.config import LogFormat, Settings

REDACTED = "[REDACTED]"

_SENSITIVE_KEY_PARTS = (
    "authorization",
    "credential",
    "password",
    "passwd",
    "private_key",
    "secret",
    "token",
    "api_key",
    "apikey",
)
_SENSITIVE_ASSIGNMENT = re.compile(
    r"(?i)\b(password|passwd|token|secret|api[_-]?key|authorization)"
    r"\s*([:=])\s*([^\s,;]+)"
)
_BEARER_TOKEN = re.compile(r"(?i)\bBearer\s+[^\s,;]+")
_PRIVATE_KEY_BLOCK = re.compile(
    r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----",
    re.DOTALL,
)


class LogEvent(StrEnum):
    """Stable event names used by the Phase 1 runtime."""

    AGENT_STARTING = "agent.starting"
    AGENT_READY = "agent.ready"
    HEARTBEAT_WRITE_FAILED = "agent.heartbeat_write_failed"
    AGENT_DEGRADED = "agent.degraded"
    SHUTDOWN_REQUESTED = "agent.shutdown_requested"
    AGENT_STOPPED = "agent.stopped"


def sanitize_text(value: str) -> str:
    """Redact common secret representations from free-form text."""
    sanitized = _PRIVATE_KEY_BLOCK.sub("[REDACTED PRIVATE KEY]", value)
    sanitized = _BEARER_TOKEN.sub(f"Bearer {REDACTED}", sanitized)
    return _SENSITIVE_ASSIGNMENT.sub(
        lambda match: f"{match.group(1)}{match.group(2)}{REDACTED}",
        sanitized,
    )


def _is_sensitive_key(key: str) -> bool:
    normalized = key.lower().replace("-", "_")
    return any(part in normalized for part in _SENSITIVE_KEY_PARTS)


def sanitize_fields(fields: Mapping[str, object]) -> dict[str, object]:
    """Return a recursively sanitized copy of structured log fields."""
    sanitized: dict[str, object] = {}
    for key, value in fields.items():
        sanitized[key] = REDACTED if _is_sensitive_key(key) else _sanitize_value(value)
    return sanitized


def _sanitize_value(value: object) -> object:
    if isinstance(value, str):
        return sanitize_text(value)
    if isinstance(value, Mapping):
        string_keyed = {str(key): nested for key, nested in value.items()}
        return sanitize_fields(string_keyed)
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [_sanitize_value(item) for item in value]
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return sanitize_text(str(value))


class JsonFormatter(logging.Formatter):
    """Render a log record using the deployed JSON contract."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "timestamp": datetime.fromtimestamp(record.created, UTC)
            .isoformat()
            .replace("+00:00", "Z"),
            "level": record.levelname,
            "event": sanitize_text(str(getattr(record, "event", "application.log"))),
            "message": sanitize_text(record.getMessage()),
        }
        agent_id = getattr(record, "agent_id", None)
        if agent_id is not None:
            payload["agent_id"] = sanitize_text(str(agent_id))

        fields = getattr(record, "fields", None)
        if isinstance(fields, Mapping):
            payload["fields"] = sanitize_fields({str(key): value for key, value in fields.items()})

        return json.dumps(payload, separators=(",", ":"), sort_keys=True)


class ConsoleFormatter(logging.Formatter):
    """Render a compact, sanitized development log line."""

    def format(self, record: logging.LogRecord) -> str:
        event = sanitize_text(str(getattr(record, "event", "application.log")))
        return f"{record.levelname} {event}: {sanitize_text(record.getMessage())}"


def configure_logging(settings: Settings, *, stream: TextIO | None = None) -> logging.Logger:
    """Configure and return the package logger for the supplied settings."""
    logger = logging.getLogger("chaos_agent")
    logger.handlers.clear()
    logger.setLevel(settings.log_level.value)
    logger.propagate = False

    handler = logging.StreamHandler(stream)
    if settings.log_format is LogFormat.JSON:
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(ConsoleFormatter())
    logger.addHandler(handler)
    return logger


def log_event(
    logger: logging.Logger,
    level: int,
    event: LogEvent,
    message: str,
    *,
    agent_id: str | None = None,
    fields: Mapping[str, object] | None = None,
) -> None:
    """Emit one stable, sanitized application event."""
    extra: dict[str, object] = {"event": event.value}
    if agent_id is not None:
        extra["agent_id"] = agent_id
    if fields is not None:
        extra["fields"] = dict(fields)
    logger.log(level, message, extra=extra)
