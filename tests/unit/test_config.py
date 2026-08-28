"""Tests for typed environment configuration."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from chaos_agent.config import Environment, LogFormat, LogLevel, Settings


def test_settings_have_safe_phase_one_defaults() -> None:
    settings = Settings(_env_file=None)

    assert settings.agent_id == "chaos-agent-dev"
    assert settings.environment is Environment.DEVELOPMENT
    assert settings.data_dir == Path("/var/lib/chaos-agent")
    assert settings.log_level is LogLevel.INFO
    assert settings.log_format is LogFormat.JSON
    assert settings.heartbeat_interval_seconds == 10
    assert settings.heartbeat_max_age_seconds == 30


def test_settings_load_prefixed_environment_variables(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CHAOS_AGENT_ID", "foundation-test")
    monkeypatch.setenv("CHAOS_DATA_DIR", "/var/lib/chaos-agent-test")
    monkeypatch.setenv("CHAOS_LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("CHAOS_LOG_FORMAT", "console")
    monkeypatch.setenv("CHAOS_HEARTBEAT_INTERVAL_SECONDS", "20")
    monkeypatch.setenv("CHAOS_HEARTBEAT_MAX_AGE_SECONDS", "45")

    settings = Settings(_env_file=None)

    assert settings.agent_id == "foundation-test"
    assert settings.data_dir == Path("/var/lib/chaos-agent-test")
    assert settings.log_level is LogLevel.DEBUG
    assert settings.log_format is LogFormat.CONSOLE
    assert settings.heartbeat_interval_seconds == 20
    assert settings.heartbeat_max_age_seconds == 45


@pytest.mark.parametrize(
    "unsafe_path",
    [
        ".",
        "relative/data",
        "/",
        "/home",
        "/home/chaos-agent",
        "/Users/developer",
        "/root",
        "/root/.ssh",
        "/run/secrets/chaos-agent/ssh",
        "/run/secrets/chaos-agent/ssh/nested",
    ],
)
def test_settings_reject_unsafe_data_directories(unsafe_path: str) -> None:
    with pytest.raises(ValidationError):
        Settings(data_dir=unsafe_path, _env_file=None)


def test_settings_reject_invalid_agent_id() -> None:
    with pytest.raises(ValidationError):
        Settings(agent_id="Agent ID With Spaces", _env_file=None)


def test_settings_reject_unsupported_environment() -> None:
    with pytest.raises(ValidationError):
        Settings(environment="production", _env_file=None)


def test_settings_reject_unknown_log_values() -> None:
    with pytest.raises(ValidationError):
        Settings(log_level="TRACE", log_format="xml", _env_file=None)


def test_settings_reject_heartbeat_max_age_without_tolerance() -> None:
    with pytest.raises(ValidationError, match="at least twice"):
        Settings(
            heartbeat_interval_seconds=20,
            heartbeat_max_age_seconds=39,
            _env_file=None,
        )
