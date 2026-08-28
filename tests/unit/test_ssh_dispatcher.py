"""Tests for exact forced-command dispatch behavior."""

import runpy
from pathlib import Path
from typing import Any, NoReturn

import pytest

DISPATCHER_PATH = Path(__file__).parents[2] / "ops/target/ssh-dispatcher"


@pytest.fixture(scope="module")
def dispatcher() -> dict[str, Any]:
    return runpy.run_path(str(DISPATCHER_PATH), run_name="ssh_dispatcher_tests")


@pytest.mark.parametrize("operation", ["version", "identity", "preflight"])
def test_dispatcher_executes_only_fixed_sudo_argv(
    dispatcher: dict[str, Any], operation: str
) -> None:
    captured: dict[str, object] = {}

    class Executed(Exception):
        pass

    def fake_execve(path: str, argv: list[str], environment: dict[str, str]) -> NoReturn:
        captured.update(path=path, argv=argv, environment=environment)
        raise Executed

    command = f"sudo -n /usr/local/libexec/chaos-agent/target-helper {operation}"
    with pytest.raises(Executed):
        dispatcher["dispatch"]({"SSH_ORIGINAL_COMMAND": command, "SECRET": "hidden"}, fake_execve)

    assert captured == {
        "path": "/usr/bin/sudo",
        "argv": [
            "/usr/bin/sudo",
            "-n",
            "/usr/local/libexec/chaos-agent/target-helper",
            operation,
        ],
        "environment": {"PATH": "/usr/sbin:/usr/bin:/sbin:/bin", "LANG": "C.UTF-8"},
    }


@pytest.mark.parametrize(
    "command",
    [
        "",
        "identity",
        "sudo -n /usr/local/libexec/chaos-agent/target-helper",
        "sudo -n /usr/local/libexec/chaos-agent/target-helper identity extra",
        "sudo -n /usr/local/libexec/chaos-agent/target-helper identity; sh",
        "sudo -n /usr/local/libexec/chaos-agent/target-helper  identity",
        "sudo -n /usr/local/libexec/chaos-agent/target-helper preflight\nwhoami",
    ],
)
def test_dispatcher_refuses_every_non_exact_command(
    dispatcher: dict[str, Any], command: str
) -> None:
    with pytest.raises(ValueError, match="command_refused"):
        dispatcher["dispatch"]({"SSH_ORIGINAL_COMMAND": command})
