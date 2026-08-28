"""Tests for the initial command-line interface."""

import json
import subprocess
import sys
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path

from typer.testing import CliRunner

from chaos_agent.cli import app, get_version
from chaos_agent.runtime import FileHeartbeatRepository, Heartbeat, RuntimeStatus

runner = CliRunner()


def test_get_version_uses_installed_package_metadata() -> None:
    assert get_version() == version("chaos-agent")


def test_version_command_returns_installed_version() -> None:
    result = runner.invoke(app, ["version"])

    assert result.exit_code == 0
    assert result.stdout.strip() == version("chaos-agent")


def test_version_command_supports_json() -> None:
    result = runner.invoke(app, ["version", "--json"])

    assert result.exit_code == 0
    assert json.loads(result.stdout) == {"version": version("chaos-agent")}


def test_config_check_reports_valid_configuration() -> None:
    result = runner.invoke(app, ["config-check"])

    assert result.exit_code == 0
    assert "Configuration is valid for agent 'chaos-agent-dev' in development." in result.stdout


def test_config_check_supports_json() -> None:
    result = runner.invoke(app, ["config-check", "--json"])

    assert result.exit_code == 0
    assert json.loads(result.stdout) == {
        "status": "valid",
        "agent_id": "chaos-agent-dev",
        "environment": "development",
    }


def test_config_check_returns_safe_json_for_invalid_configuration() -> None:
    secret_input = "invalid secret token=do-not-print"
    result = runner.invoke(
        app,
        ["config-check", "--json"],
        env={"CHAOS_AGENT_ID": secret_input},
    )

    assert result.exit_code == 2
    payload = json.loads(result.stdout)
    assert payload["status"] == "invalid"
    assert payload["errors"][0]["field"] == "agent_id"
    assert secret_input not in result.stdout
    assert "do-not-print" not in result.stdout


def test_config_check_returns_safe_human_error() -> None:
    result = runner.invoke(
        app,
        ["config-check"],
        env={"CHAOS_DATA_DIR": "password=do-not-print"},
    )

    assert result.exit_code == 2
    assert result.stdout.startswith("Configuration is invalid:")
    assert "do-not-print" not in result.stdout


def test_health_reports_healthy_runtime_in_json(tmp_path: Path) -> None:
    now = datetime.now(UTC)
    FileHeartbeatRepository(tmp_path).write(
        Heartbeat(
            agent_id="chaos-agent-dev",
            process_started_at=now,
            last_heartbeat_at=now,
            status=RuntimeStatus.READY,
        )
    )

    result = runner.invoke(
        app,
        ["health", "--json"],
        env={"CHAOS_DATA_DIR": str(tmp_path)},
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["status"] == "healthy"
    assert payload["agent_id"] == "chaos-agent-dev"
    assert {check["name"] for check in payload["checks"]} == {
        "data_directory",
        "runtime_heartbeat",
    }


def test_health_reports_stopped_runtime_as_unhealthy(tmp_path: Path) -> None:
    now = datetime.now(UTC)
    FileHeartbeatRepository(tmp_path).write(
        Heartbeat(
            agent_id="chaos-agent-dev",
            process_started_at=now,
            last_heartbeat_at=now,
            status=RuntimeStatus.STOPPED,
        )
    )

    result = runner.invoke(app, ["health"], env={"CHAOS_DATA_DIR": str(tmp_path)})

    assert result.exit_code == 1
    assert result.stdout.startswith("Agent health: unhealthy")
    assert "runtime is not ready" in result.stdout


def test_health_returns_safe_failure_for_invalid_configuration() -> None:
    result = runner.invoke(
        app,
        ["health", "--json"],
        env={"CHAOS_AGENT_ID": "invalid token=health-secret"},
    )

    assert result.exit_code == 1
    assert json.loads(result.stdout) == {
        "status": "unhealthy",
        "checks": [
            {
                "name": "configuration",
                "status": "fail",
                "message": "configuration is invalid",
            }
        ],
    }
    assert "health-secret" not in result.stdout


def test_module_entry_point_returns_installed_version() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "chaos_agent", "version"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert result.stdout.strip() == version("chaos-agent")
    assert result.stderr == ""


def test_no_arguments_shows_help_without_a_traceback() -> None:
    result = runner.invoke(app, [])

    assert result.exit_code == 0
    assert "Safely coordinate controlled chaos experiments" in result.stdout
    assert "Traceback" not in result.stdout
