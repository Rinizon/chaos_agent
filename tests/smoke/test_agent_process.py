"""Process-level smoke tests for graceful passive runtime shutdown."""

import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path


def wait_for_heartbeat(path: Path, timeout_seconds: float = 5.0) -> dict[str, object]:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError):
            time.sleep(0.01)
    raise AssertionError("agent did not produce a readable heartbeat before the deadline")


def test_agent_process_handles_sigterm_and_marks_heartbeat_stopped(tmp_path: Path) -> None:
    environment = os.environ.copy()
    environment.update(
        {
            "CHAOS_DATA_DIR": str(tmp_path),
            "CHAOS_LOG_FORMAT": "json",
            "CHAOS_HEARTBEAT_INTERVAL_SECONDS": "1",
            "CHAOS_HEARTBEAT_MAX_AGE_SECONDS": "2",
        }
    )
    process = subprocess.Popen(
        [sys.executable, "-m", "chaos_agent", "agent"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=environment,
    )

    heartbeat_path = tmp_path / "agent-status.json"
    heartbeat = wait_for_heartbeat(heartbeat_path)
    assert heartbeat["status"] == "ready"

    process.send_signal(signal.SIGTERM)
    stdout, stderr = process.communicate(timeout=5)

    assert process.returncode == 0
    assert stdout == ""
    events = [json.loads(line)["event"] for line in stderr.splitlines()]
    assert events == [
        "agent.starting",
        "agent.ready",
        "agent.shutdown_requested",
        "agent.stopped",
    ]
    assert wait_for_heartbeat(heartbeat_path)["status"] == "stopped"
