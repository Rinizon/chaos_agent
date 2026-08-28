"""Local-only health evaluation for the passive agent runtime."""

import os
from dataclasses import asdict, dataclass
from enum import StrEnum

from chaos_agent.config import Settings
from chaos_agent.runtime import (
    Clock,
    FileHeartbeatRepository,
    Heartbeat,
    HeartbeatRepository,
    HeartbeatUnavailable,
    RuntimeStatus,
    SystemClock,
)


class CheckStatus(StrEnum):
    """Outcome of one local health check."""

    PASS = "pass"
    FAIL = "fail"


class HealthStatus(StrEnum):
    """Aggregate local agent health status."""

    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"


@dataclass(frozen=True)
class HealthCheck:
    """One sanitized local health result."""

    name: str
    status: CheckStatus
    message: str

    def to_dict(self) -> dict[str, str]:
        return {key: str(value) for key, value in asdict(self).items()}


@dataclass(frozen=True)
class HealthReport:
    """Aggregate local agent health report."""

    status: HealthStatus
    agent_id: str
    checks: tuple[HealthCheck, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "status": self.status.value,
            "agent_id": self.agent_id,
            "checks": [check.to_dict() for check in self.checks],
        }


def unhealthy_configuration_report() -> dict[str, object]:
    """Return a safe health response when configuration cannot be loaded."""
    return {
        "status": HealthStatus.UNHEALTHY.value,
        "checks": [
            {
                "name": "configuration",
                "status": CheckStatus.FAIL.value,
                "message": "configuration is invalid",
            }
        ],
    }


def evaluate_health(
    settings: Settings,
    *,
    repository: HeartbeatRepository | None = None,
    clock: Clock | None = None,
) -> HealthReport:
    """Evaluate local storage and heartbeat readiness without remote checks."""
    checks: list[HealthCheck] = []
    if not settings.data_dir.exists():
        checks.append(HealthCheck("data_directory", CheckStatus.FAIL, "data directory is missing"))
    elif not settings.data_dir.is_dir():
        checks.append(
            HealthCheck("data_directory", CheckStatus.FAIL, "data directory is not a directory")
        )
    elif not os.access(settings.data_dir, os.W_OK):
        checks.append(
            HealthCheck("data_directory", CheckStatus.FAIL, "data directory is not writable")
        )
    else:
        checks.append(HealthCheck("data_directory", CheckStatus.PASS, "data directory is usable"))

    heartbeat_repository = repository or FileHeartbeatRepository(settings.data_dir)
    current_clock = clock or SystemClock()
    try:
        heartbeat = heartbeat_repository.read()
    except HeartbeatUnavailable as error:
        checks.append(HealthCheck("runtime_heartbeat", CheckStatus.FAIL, str(error)))
    else:
        heartbeat_failure = _heartbeat_failure(settings, heartbeat, current_clock)
        if heartbeat_failure is None:
            checks.append(
                HealthCheck("runtime_heartbeat", CheckStatus.PASS, "heartbeat is current")
            )
        else:
            checks.append(HealthCheck("runtime_heartbeat", CheckStatus.FAIL, heartbeat_failure))

    status = (
        HealthStatus.HEALTHY
        if all(check.status is CheckStatus.PASS for check in checks)
        else HealthStatus.UNHEALTHY
    )
    return HealthReport(status, settings.agent_id, tuple(checks))


def _heartbeat_failure(settings: Settings, heartbeat: Heartbeat, clock: Clock) -> str | None:
    if heartbeat.agent_id != settings.agent_id:
        return "heartbeat belongs to a different agent"
    if heartbeat.status is not RuntimeStatus.READY:
        return "runtime is not ready"

    age_seconds = (clock.now() - heartbeat.last_heartbeat_at).total_seconds()
    if age_seconds < -settings.heartbeat_interval_seconds:
        return "heartbeat timestamp is unexpectedly in the future"
    if age_seconds > settings.heartbeat_max_age_seconds:
        return "heartbeat is stale"
    return None
