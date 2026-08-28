"""Tests for passive runtime state and heartbeat persistence."""

import json
import logging
import signal
import stat
from datetime import UTC, datetime, timedelta
from io import StringIO
from pathlib import Path
from threading import Event

import pytest

from chaos_agent.config import LogFormat, Settings
from chaos_agent.logging import configure_logging
from chaos_agent.runtime import (
    FileHeartbeatRepository,
    Heartbeat,
    HeartbeatUnavailable,
    HeartbeatWriteError,
    PassiveRuntime,
    RuntimeStatus,
    signal_shutdown,
)


class FakeClock:
    def __init__(self, now: datetime) -> None:
        self.value = now

    def now(self) -> datetime:
        return self.value


class RecordingRepository:
    def __init__(self, *, fail_on_write: int | None = None) -> None:
        self.writes: list[Heartbeat] = []
        self.write_attempts = 0
        self.fail_on_write = fail_on_write
        self.invalidated = False

    def write(self, heartbeat: Heartbeat) -> None:
        self.write_attempts += 1
        if self.write_attempts == self.fail_on_write:
            raise HeartbeatWriteError("simulated write failure")
        self.writes.append(heartbeat)

    def read(self) -> Heartbeat:
        if not self.writes:
            raise HeartbeatUnavailable("runtime heartbeat is missing")
        return self.writes[-1]

    def invalidate(self) -> None:
        self.invalidated = True


def build_settings(data_dir: Path) -> Settings:
    return Settings(
        data_dir=data_dir,
        log_format=LogFormat.JSON,
        heartbeat_interval_seconds=1,
        heartbeat_max_age_seconds=2,
        _env_file=None,
    )


def test_file_repository_writes_atomically_with_restrictive_permissions(tmp_path: Path) -> None:
    data_dir = tmp_path / "runtime-data"
    repository = FileHeartbeatRepository(data_dir)
    now = datetime(2026, 8, 28, 12, 0, tzinfo=UTC)
    heartbeat = Heartbeat(
        agent_id="chaos-agent-dev",
        process_started_at=now,
        last_heartbeat_at=now,
        status=RuntimeStatus.READY,
    )

    repository.write(heartbeat)

    assert repository.read() == heartbeat
    assert stat.S_IMODE(repository.path.stat().st_mode) == 0o600
    assert list(data_dir.glob("*.tmp")) == []
    serialized = json.loads(repository.path.read_text(encoding="utf-8"))
    assert serialized["schema_version"] == 1
    assert "secret" not in serialized


def test_file_repository_reports_missing_and_malformed_heartbeat(tmp_path: Path) -> None:
    repository = FileHeartbeatRepository(tmp_path)
    with pytest.raises(HeartbeatUnavailable, match="missing"):
        repository.read()

    repository.path.write_text("not-json", encoding="utf-8")
    with pytest.raises(HeartbeatUnavailable, match="unreadable or invalid"):
        repository.read()


def test_runtime_updates_heartbeat_and_marks_it_stopped_without_sleeping(tmp_path: Path) -> None:
    now = datetime(2026, 8, 28, 12, 0, tzinfo=UTC)
    clock = FakeClock(now)
    repository = RecordingRepository()
    logger = configure_logging(build_settings(tmp_path), stream=StringIO())
    wait_count = 0

    def wait_for_stop(_timeout: float) -> bool:
        nonlocal wait_count
        wait_count += 1
        clock.value += timedelta(seconds=1)
        return wait_count == 2

    runtime = PassiveRuntime(
        build_settings(tmp_path),
        repository,
        logger,
        clock=clock,
        wait_for_stop=wait_for_stop,
    )

    assert runtime.run() == 0
    assert [heartbeat.status for heartbeat in repository.writes] == [
        RuntimeStatus.READY,
        RuntimeStatus.READY,
        RuntimeStatus.STOPPED,
    ]
    assert repository.writes[-1].last_heartbeat_at == now + timedelta(seconds=2)


def test_runtime_invalidates_heartbeat_when_initial_write_fails(tmp_path: Path) -> None:
    stream = StringIO()
    settings = build_settings(tmp_path)
    repository = RecordingRepository(fail_on_write=1)
    runtime = PassiveRuntime(
        settings,
        repository,
        configure_logging(settings, stream=stream),
        clock=FakeClock(datetime(2026, 8, 28, 12, 0, tzinfo=UTC)),
        wait_for_stop=lambda _timeout: True,
    )

    assert runtime.run() == 1
    assert repository.invalidated is True
    events = [json.loads(line)["event"] for line in stream.getvalue().splitlines()]
    assert events == [
        "agent.starting",
        "agent.heartbeat_write_failed",
        "agent.degraded",
    ]


def test_runtime_invalidates_heartbeat_when_stopped_state_cannot_be_written(tmp_path: Path) -> None:
    settings = build_settings(tmp_path)
    repository = RecordingRepository(fail_on_write=2)
    runtime = PassiveRuntime(
        settings,
        repository,
        logging.getLogger("test-runtime-stop-failure"),
        clock=FakeClock(datetime(2026, 8, 28, 12, 0, tzinfo=UTC)),
        wait_for_stop=lambda _timeout: True,
    )

    assert runtime.run() == 1
    assert repository.invalidated is True


def test_signal_shutdown_sets_event_and_restores_handler() -> None:
    stop_event = Event()
    previous_handler = signal.getsignal(signal.SIGTERM)

    with signal_shutdown(stop_event):
        installed_handler = signal.getsignal(signal.SIGTERM)
        assert callable(installed_handler)
        installed_handler(signal.SIGTERM, None)
        assert stop_event.is_set()

    assert signal.getsignal(signal.SIGTERM) == previous_handler
