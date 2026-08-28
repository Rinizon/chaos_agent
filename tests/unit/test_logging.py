"""Tests for structured and sanitized application logging."""

import json
import logging
from io import StringIO

from chaos_agent.config import LogFormat, Settings
from chaos_agent.logging import (
    REDACTED,
    LogEvent,
    configure_logging,
    log_event,
    sanitize_fields,
    sanitize_text,
)


def test_sanitize_text_redacts_assignments_bearer_tokens_and_private_keys() -> None:
    private_key = "-----BEGIN PRIVATE KEY-----\nvery-secret\n-----END PRIVATE KEY-----"
    text = (
        "password=hunter2 token:abc123 Authorization=BasicSecret "
        f"Bearer bearer-secret {private_key}"
    )

    sanitized = sanitize_text(text)

    for secret in ("hunter2", "abc123", "BasicSecret", "bearer-secret", "very-secret"):
        assert secret not in sanitized
    assert REDACTED in sanitized
    assert "[REDACTED PRIVATE KEY]" in sanitized


def test_sanitize_fields_recursively_redacts_sensitive_keys() -> None:
    fields = {
        "target": "development",
        "api-key": "outer-secret",
        "nested": {"password": "nested-secret", "note": "token=inline-secret"},
        "items": [{"authorization": "item-secret"}],
    }

    sanitized = sanitize_fields(fields)
    serialized = json.dumps(sanitized)

    assert sanitized["target"] == "development"
    for secret in ("outer-secret", "nested-secret", "inline-secret", "item-secret"):
        assert secret not in serialized


def test_json_logging_emits_contract_and_redacts_secrets() -> None:
    stream = StringIO()
    settings = Settings(log_format=LogFormat.JSON, _env_file=None)
    logger = configure_logging(settings, stream=stream)

    log_event(
        logger,
        logging.INFO,
        LogEvent.AGENT_STARTING,
        "starting with token=message-secret",
        agent_id=settings.agent_id,
        fields={"password": "field-secret", "mode": "passive"},
    )

    output = stream.getvalue()
    payload = json.loads(output)
    assert payload["timestamp"].endswith("Z")
    assert payload["level"] == "INFO"
    assert payload["event"] == "agent.starting"
    assert payload["agent_id"] == "chaos-agent-dev"
    assert payload["fields"] == {"mode": "passive", "password": REDACTED}
    assert "message-secret" not in output
    assert "field-secret" not in output


def test_console_logging_is_sanitized() -> None:
    stream = StringIO()
    settings = Settings(log_format=LogFormat.CONSOLE, _env_file=None)
    logger = configure_logging(settings, stream=stream)

    log_event(
        logger,
        logging.WARNING,
        LogEvent.AGENT_DEGRADED,
        "authorization=console-secret",
    )

    output = stream.getvalue()
    assert output.startswith("WARNING agent.degraded:")
    assert "console-secret" not in output
    assert REDACTED in output
