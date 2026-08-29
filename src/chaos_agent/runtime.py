"""Passive agent runtime and atomic heartbeat persistence."""

import json
import logging
import os
import signal
import tempfile
from collections.abc import Callable, Iterator
from contextlib import contextmanager, suppress
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from threading import Event
from types import FrameType
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, ValidationError, model_validator

from chaos_agent.config import Settings
from chaos_agent.logging import LogEvent, log_event

HEARTBEAT_SCHEMA_VERSION = 1
HEARTBEAT_FILENAME = "agent-status.json"


class RuntimeStatus(StrEnum):
    """States exposed through the local runtime heartbeat."""

    READY = "ready"
    DEGRADED = "degraded"
    STOPPED = "stopped"


class Heartbeat(BaseModel):
    """Versioned, non-secret local runtime status document."""

    model_config = ConfigDict(extra="forbid")

    schema_version: int = HEARTBEAT_SCHEMA_VERSION
    agent_id: str
    process_started_at: datetime
    last_heartbeat_at: datetime
    status: RuntimeStatus

    @model_validator(mode="after")
    def validate_timestamps(self) -> "Heartbeat":
        """Require ordered, timezone-aware runtime timestamps."""
        if self.process_started_at.tzinfo is None or self.last_heartbeat_at.tzinfo is None:
            raise ValueError("heartbeat timestamps must include a timezone")
        if self.last_heartbeat_at < self.process_started_at:
            raise ValueError("heartbeat time must not precede process start time")
        if self.schema_version != HEARTBEAT_SCHEMA_VERSION:
            raise ValueError("unsupported heartbeat schema version")
        return self


class Clock(Protocol):
    """Clock seam used for deterministic runtime and health tests."""

    def now(self) -> datetime:
        """Return the current timezone-aware UTC time."""


class SystemClock:
    """Production UTC clock."""

    def now(self) -> datetime:
        return datetime.now(UTC)


class HeartbeatError(RuntimeError):
    """Base class for safe heartbeat storage failures."""


class HeartbeatUnavailable(HeartbeatError):
    """Heartbeat cannot be read or validated."""


class HeartbeatWriteError(HeartbeatError):
    """Heartbeat cannot be written atomically."""


class HeartbeatRepository(Protocol):
    """Storage seam for runtime and health behavior."""

    def write(self, heartbeat: Heartbeat) -> None:
        """Persist a complete heartbeat atomically."""

    def read(self) -> Heartbeat:
        """Read and validate the current heartbeat."""

    def invalidate(self) -> None:
        """Ensure a previous ready heartbeat cannot remain authoritative."""


class FileHeartbeatRepository:
    """Store a heartbeat atomically in the configured data directory."""

    def __init__(self, data_dir: Path) -> None:
        self.data_dir = data_dir
        self.path = data_dir / HEARTBEAT_FILENAME

    def write(self, heartbeat: Heartbeat) -> None:
        descriptor: int | None = None
        temporary_path: Path | None = None
        try:
            self.data_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
            descriptor, temporary_name = tempfile.mkstemp(
                dir=self.data_dir,
                prefix=f".{HEARTBEAT_FILENAME}.",
                suffix=".tmp",
            )
            temporary_path = Path(temporary_name)
            os.chmod(temporary_path, 0o600)
            temporary_file = os.fdopen(descriptor, "w", encoding="utf-8")
            descriptor = None
            with temporary_file:
                json.dump(heartbeat.model_dump(mode="json"), temporary_file, separators=(",", ":"))
                temporary_file.write("\n")
                temporary_file.flush()
                os.fsync(temporary_file.fileno())
            os.replace(temporary_path, self.path)
        except (OSError, TypeError, ValueError) as error:
            if descriptor is not None:
                with suppress(OSError):
                    os.close(descriptor)
            if temporary_path is not None:
                with suppress(OSError):
                    temporary_path.unlink(missing_ok=True)
            raise HeartbeatWriteError("unable to write runtime heartbeat") from error

    def read(self) -> Heartbeat:
        try:
            content = self.path.read_text(encoding="utf-8")
            return Heartbeat.model_validate_json(content)
        except FileNotFoundError as error:
            raise HeartbeatUnavailable("runtime heartbeat is missing") from error
        except (OSError, ValidationError) as error:
            raise HeartbeatUnavailable("runtime heartbeat is unreadable or invalid") from error

    def invalidate(self) -> None:
        try:
            self.path.unlink(missing_ok=True)
        except OSError as error:
            raise HeartbeatWriteError("unable to invalidate runtime heartbeat") from error


WaitForStop = Callable[[float], bool]
SupervisorTick = Callable[[], None]
SignalHandler = Callable[[int, FrameType | None], Any] | int | None


class PassiveRuntime:
    """Non-disruptive long-running process used as the container runtime."""

    def __init__(
        self,
        settings: Settings,
        repository: HeartbeatRepository,
        logger: logging.Logger,
        *,
        clock: Clock | None = None,
        wait_for_stop: WaitForStop,
        supervisor_tick: SupervisorTick | None = None,
    ) -> None:
        self.settings = settings
        self.repository = repository
        self.logger = logger
        self.clock = clock or SystemClock()
        self.wait_for_stop = wait_for_stop
        self.supervisor_tick = supervisor_tick

    def run(self) -> int:
        """Run until stopped, returning non-zero when heartbeat safety fails."""
        process_started_at = self.clock.now()
        log_event(
            self.logger,
            logging.INFO,
            LogEvent.AGENT_STARTING,
            "passive agent runtime is starting",
            agent_id=self.settings.agent_id,
        )

        if not self._write_heartbeat(process_started_at, RuntimeStatus.READY):
            self._invalidate_after_failure()
            return 1

        log_event(
            self.logger,
            logging.INFO,
            LogEvent.AGENT_READY,
            "passive agent runtime is ready",
            agent_id=self.settings.agent_id,
        )

        while not self.wait_for_stop(float(self.settings.heartbeat_interval_seconds)):
            if self.supervisor_tick is not None:
                try:
                    self.supervisor_tick()
                except Exception:
                    log_event(
                        self.logger, logging.ERROR, LogEvent.AGENT_DEGRADED,
                        "supervisor tick failed", agent_id=self.settings.agent_id,
                    )
            if not self._write_heartbeat(process_started_at, RuntimeStatus.READY):
                self._invalidate_after_failure()
                return 1

        log_event(
            self.logger,
            logging.INFO,
            LogEvent.SHUTDOWN_REQUESTED,
            "agent shutdown was requested",
            agent_id=self.settings.agent_id,
        )
        exit_code = 0
        if not self._write_heartbeat(process_started_at, RuntimeStatus.STOPPED):
            self._invalidate_after_failure()
            exit_code = 1

        log_event(
            self.logger,
            logging.INFO,
            LogEvent.AGENT_STOPPED,
            "passive agent runtime stopped",
            agent_id=self.settings.agent_id,
            fields={"exit_code": exit_code},
        )
        return exit_code

    def _write_heartbeat(self, process_started_at: datetime, status: RuntimeStatus) -> bool:
        heartbeat = Heartbeat(
            agent_id=self.settings.agent_id,
            process_started_at=process_started_at,
            last_heartbeat_at=self.clock.now(),
            status=status,
        )
        try:
            self.repository.write(heartbeat)
        except HeartbeatWriteError:
            log_event(
                self.logger,
                logging.ERROR,
                LogEvent.HEARTBEAT_WRITE_FAILED,
                "runtime heartbeat could not be written",
                agent_id=self.settings.agent_id,
            )
            log_event(
                self.logger,
                logging.ERROR,
                LogEvent.AGENT_DEGRADED,
                "agent cannot safely report local runtime health",
                agent_id=self.settings.agent_id,
            )
            return False
        return True

    def _invalidate_after_failure(self) -> None:
        try:
            self.repository.invalidate()
        except HeartbeatWriteError:
            log_event(
                self.logger,
                logging.ERROR,
                LogEvent.AGENT_DEGRADED,
                "previous runtime heartbeat could not be invalidated",
                agent_id=self.settings.agent_id,
            )


@contextmanager
def signal_shutdown(stop_event: Event) -> Iterator[None]:
    """Translate SIGTERM and SIGINT into the runtime stop event."""
    previous_handlers: dict[signal.Signals, SignalHandler] = {}

    def request_shutdown(_signal_number: int, _frame: FrameType | None) -> None:
        stop_event.set()

    for signal_number in (signal.SIGTERM, signal.SIGINT):
        previous_handlers[signal_number] = signal.getsignal(signal_number)
        signal.signal(signal_number, request_shutdown)

    try:
        yield
    finally:
        for signal_number, previous_handler in previous_handlers.items():
            signal.signal(signal_number, previous_handler)


def run_passive_agent(settings: Settings, logger: logging.Logger) -> int:
    """Run the production passive runtime with filesystem and signal adapters."""
    stop_event = Event()
    runtime = PassiveRuntime(
        settings,
        FileHeartbeatRepository(settings.data_dir),
        logger,
        wait_for_stop=stop_event.wait,
    )
    with signal_shutdown(stop_event):
        return runtime.run()
