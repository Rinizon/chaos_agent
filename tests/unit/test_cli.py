"""Tests for the initial command-line interface."""

import json
import subprocess
import sys
from importlib.metadata import version

from typer.testing import CliRunner

from chaos_agent.cli import app, get_version

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
