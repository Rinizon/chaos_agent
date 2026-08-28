"""Tests for local-only agent health evaluation."""

import os
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from chaos_agent.config import Settings
from chaos_agent.health import CheckStatus, HealthStatus, evaluate_health
from chaos_agent.runtime import FileHeartbeatRepository, Heartbeat, RuntimeStatus


class FakeClock:
    def __init__(self, now: datetime) -> None:
        self.value = now

    def now(self) -> datetime:
        return self.value


def build_settings(data_dir: Path) -> Settings:
    return Settings(
        data_dir=data_dir,
        heartbeat_interval_seconds=10,
        heartbeat_max_age_seconds=30,
        _env_file=None,
    )


def write_heartbeat(
    settings: Settings,
    now: datetime,
    *,
    agent_id: str | None = None,
    status: RuntimeStatus = RuntimeStatus.READY,
    age: timedelta = timedelta(),
) -> None:
    FileHeartbeatRepository(settings.data_dir).write(
        Heartbeat(
            agent_id=agent_id or settings.agent_id,
            process_started_at=now - timedelta(minutes=1),
            last_heartbeat_at=now - age,
            status=status,
        )
    )


def test_current_matching_ready_heartbeat_is_healthy(tmp_path: Path) -> None:
    now = datetime(2026, 8, 28, 12, 0, tzinfo=UTC)
    settings = build_settings(tmp_path)
    write_heartbeat(settings, now)

    report = evaluate_health(settings, clock=FakeClock(now))

    assert report.status is HealthStatus.HEALTHY
    assert all(check.status is CheckStatus.PASS for check in report.checks)
    assert report.to_dict()["status"] == "healthy"


def test_missing_data_and_heartbeat_are_unhealthy(tmp_path: Path) -> None:
    settings = build_settings(tmp_path / "missing")

    report = evaluate_health(settings)

    assert report.status is HealthStatus.UNHEALTHY
    assert [check.name for check in report.checks] == ["data_directory", "runtime_heartbeat"]
    assert all(check.status is CheckStatus.FAIL for check in report.checks)


def test_stale_heartbeat_is_unhealthy(tmp_path: Path) -> None:
    now = datetime(2026, 8, 28, 12, 0, tzinfo=UTC)
    settings = build_settings(tmp_path)
    write_heartbeat(settings, now, age=timedelta(seconds=31))

    report = evaluate_health(settings, clock=FakeClock(now))

    assert report.status is HealthStatus.UNHEALTHY
    assert report.checks[-1].message == "heartbeat is stale"


def test_future_heartbeat_is_unhealthy(tmp_path: Path) -> None:
    now = datetime(2026, 8, 28, 12, 0, tzinfo=UTC)
    settings = build_settings(tmp_path)
    write_heartbeat(settings, now, age=timedelta(seconds=-11))

    report = evaluate_health(settings, clock=FakeClock(now))

    assert report.status is HealthStatus.UNHEALTHY
    assert report.checks[-1].message == "heartbeat timestamp is unexpectedly in the future"


def test_mismatched_agent_is_unhealthy(tmp_path: Path) -> None:
    now = datetime(2026, 8, 28, 12, 0, tzinfo=UTC)
    settings = build_settings(tmp_path)
    write_heartbeat(settings, now, agent_id="different-agent")

    report = evaluate_health(settings, clock=FakeClock(now))

    assert report.status is HealthStatus.UNHEALTHY
    assert report.checks[-1].message == "heartbeat belongs to a different agent"


def test_stopped_runtime_is_unhealthy(tmp_path: Path) -> None:
    now = datetime(2026, 8, 28, 12, 0, tzinfo=UTC)
    settings = build_settings(tmp_path)
    write_heartbeat(settings, now, status=RuntimeStatus.STOPPED)

    report = evaluate_health(settings, clock=FakeClock(now))

    assert report.status is HealthStatus.UNHEALTHY
    assert report.checks[-1].message == "runtime is not ready"


def test_malformed_heartbeat_is_unhealthy(tmp_path: Path) -> None:
    settings = build_settings(tmp_path)
    tmp_path.mkdir(exist_ok=True)
    (tmp_path / "agent-status.json").write_text("{malformed", encoding="utf-8")

    report = evaluate_health(settings)

    assert report.status is HealthStatus.UNHEALTHY
    assert report.checks[-1].message == "runtime heartbeat is unreadable or invalid"


def test_unwritable_data_directory_is_unhealthy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    now = datetime(2026, 8, 28, 12, 0, tzinfo=UTC)
    settings = build_settings(tmp_path)
    write_heartbeat(settings, now)
    original_access = os.access

    def deny_write(path: os.PathLike[str], mode: int) -> bool:
        if Path(path) == tmp_path and mode == os.W_OK:
            return False
        return original_access(path, mode)

    monkeypatch.setattr("chaos_agent.health.os.access", deny_write)

    report = evaluate_health(settings, clock=FakeClock(now))

    assert report.status is HealthStatus.UNHEALTHY
    assert report.checks[0].message == "data directory is not writable"
