"""Ordered, read-only target preflight application service."""

import logging
import time
from collections.abc import Callable
from datetime import UTC, datetime

from chaos_agent.application.observer import SiteObservationError, SiteObserver
from chaos_agent.application.remote import RemoteTransport, RemoteTransportError, TransportFailure
from chaos_agent.config import LocalAccessFileError, TargetAccessConfig, validate_access_files
from chaos_agent.domain.preflight import (
    PreflightCheck,
    PreflightCheckStatus,
    PreflightOutcome,
    PreflightReport,
)
from chaos_agent.domain.target import (
    HelperVersionResponse,
    IdentityResponse,
    PreflightResponse,
    RemoteOperation,
    TargetExpectation,
    TargetIdentityRefused,
    verify_target_identity,
)
from chaos_agent.logging import LogEvent, log_event

CHECK_NAMES = (
    "configuration",
    "openssh_client",
    "ssh_files",
    "helper_version",
    "target_identity",
    "helper_preflight",
    "apache",
    "root_space",
    "memory",
    "load",
    "website",
)


class PreflightService:
    """Orchestrate preflight checks without mutating or repairing the target."""

    def __init__(
        self,
        remote: RemoteTransport,
        observer: SiteObserver,
        *,
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
        monotonic: Callable[[], float] = time.monotonic,
        logger: logging.Logger | None = None,
    ) -> None:
        self._remote = remote
        self._observer = observer
        self._now = now
        self._monotonic = monotonic
        self._logger = logger or logging.getLogger("chaos_agent")

    async def run(self, config: TargetAccessConfig) -> PreflightReport:
        started_at = self._now()
        checks: list[PreflightCheck] = []
        expectation = TargetExpectation(
            target_id=config.target_id,
            apache_service=config.apache_service,
        )
        self._pass(checks, "configuration", "Validated target configuration")

        check_started = self._monotonic()
        try:
            client_version = await self._remote.check_client()
        except RemoteTransportError as error:
            return self._failure(
                config,
                started_at,
                checks,
                "openssh_client",
                PreflightOutcome.ERROR,
                error.category.value,
                "OpenSSH client validation failed",
                check_started,
            )
        self._pass(checks, "openssh_client", f"Supported {client_version}", check_started)

        check_started = self._monotonic()
        try:
            validate_access_files(config)
        except LocalAccessFileError as error:
            return self._failure(
                config,
                started_at,
                checks,
                "ssh_files",
                PreflightOutcome.ERROR,
                f"{error.setting}_{error.issue.value}",
                "Local access-file validation failed",
                check_started,
            )
        self._pass(checks, "ssh_files", "Local SSH files are safe", check_started)

        version = await self._remote_check(
            config, started_at, checks, RemoteOperation.VERSION, "helper_version"
        )
        if isinstance(version, PreflightReport):
            return version
        if not isinstance(version, HelperVersionResponse):
            return self._protocol_failure(config, started_at, checks, "helper_version")
        if _helper_major(version.helper_version) != 0:
            return self._failure(
                config,
                started_at,
                checks,
                "helper_version",
                PreflightOutcome.REFUSED,
                "helper_version_unsupported",
                "Target helper version is unsupported",
            )
        self._pass(checks, "helper_version", "Target helper protocol is supported")

        identity = await self._remote_check(
            config, started_at, checks, RemoteOperation.IDENTITY, "target_identity"
        )
        if isinstance(identity, PreflightReport):
            return identity
        if not isinstance(identity, IdentityResponse):
            return self._protocol_failure(config, started_at, checks, "target_identity")
        refused = self._verify_identity(config, started_at, checks, expectation, identity)
        if refused is not None:
            return refused
        self._pass(checks, "target_identity", "Expected development web target verified")

        remote_preflight = await self._remote_check(
            config, started_at, checks, RemoteOperation.PREFLIGHT, "helper_preflight"
        )
        if isinstance(remote_preflight, PreflightReport):
            return remote_preflight
        if not isinstance(remote_preflight, PreflightResponse):
            return self._protocol_failure(config, started_at, checks, "helper_preflight")
        refused = self._verify_identity(
            config, started_at, checks, expectation, remote_preflight, "helper_preflight"
        )
        if refused is not None:
            return refused
        self._pass(checks, "helper_preflight", "Scoped read-only helper executed as root")

        apache = remote_preflight.apache
        if (
            apache.service != config.apache_service.value
            or not apache.installed
            or not apache.active
        ):
            return self._refusal(
                config, started_at, checks, "apache", "apache_unhealthy", "Apache baseline failed"
            )
        self._pass(checks, "apache", "Expected Apache service is installed and active")

        resources = remote_preflight.resources
        if resources.root_free_bytes < config.min_root_free_mib * 1024 * 1024:
            return self._refusal(
                config,
                started_at,
                checks,
                "root_space",
                "root_space_reserve_low",
                "Root filesystem reserve is below policy",
            )
        self._pass(checks, "root_space", "Root filesystem reserve meets policy")

        if resources.memory_available_bytes < config.min_memory_available_mib * 1024 * 1024:
            return self._refusal(
                config,
                started_at,
                checks,
                "memory",
                "memory_reserve_low",
                "Available-memory reserve is below policy",
            )
        self._pass(checks, "memory", "Available-memory reserve meets policy")

        load_per_cpu = resources.load_1m / resources.logical_cpu_count
        if load_per_cpu > float(config.max_load_per_cpu):
            return self._refusal(
                config,
                started_at,
                checks,
                "load",
                "load_above_limit",
                "Normalized load is above policy",
            )
        self._pass(checks, "load", "Normalized load meets policy")

        check_started = self._monotonic()
        try:
            observation = await self._observer.observe(config)
        except SiteObservationError as error:
            return self._failure(
                config,
                started_at,
                checks,
                "website",
                PreflightOutcome.REFUSED,
                error.category.value,
                "External website observation failed",
                check_started,
            )
        if observation.status_code != config.site_expected_status:
            return self._refusal(
                config,
                started_at,
                checks,
                "website",
                "website_status_mismatch",
                "Website status did not match policy",
                check_started,
            )
        if not observation.content_matched:
            return self._refusal(
                config,
                started_at,
                checks,
                "website",
                "website_content_mismatch",
                "Website content marker did not match",
                check_started,
            )
        self._pass(checks, "website", "External website baseline is healthy", check_started)
        return self._report(config, started_at, checks, PreflightOutcome.PASS, None)

    async def _remote_check(
        self,
        config: TargetAccessConfig,
        started_at: datetime,
        checks: list[PreflightCheck],
        operation: RemoteOperation,
        check_name: str,
    ) -> object:
        try:
            return await self._remote.execute(config, operation)
        except RemoteTransportError as error:
            outcome = (
                PreflightOutcome.REFUSED
                if error.category is TransportFailure.REMOTE_PRIVILEGE_REFUSED
                else PreflightOutcome.ERROR
            )
            return self._failure(
                config,
                started_at,
                checks,
                check_name,
                outcome,
                error.category.value,
                "Remote transport check failed",
            )

    def _verify_identity(
        self,
        config: TargetAccessConfig,
        started_at: datetime,
        checks: list[PreflightCheck],
        expectation: TargetExpectation,
        response: IdentityResponse | PreflightResponse,
        check_name: str = "target_identity",
    ) -> PreflightReport | None:
        try:
            verify_target_identity(expectation, response)
        except TargetIdentityRefused as error:
            return self._failure(
                config,
                started_at,
                checks,
                check_name,
                PreflightOutcome.REFUSED,
                error.code.value,
                "Target identity was refused",
            )
        return None

    def _protocol_failure(
        self,
        config: TargetAccessConfig,
        started_at: datetime,
        checks: list[PreflightCheck],
        check_name: str,
    ) -> PreflightReport:
        return self._failure(
            config,
            started_at,
            checks,
            check_name,
            PreflightOutcome.ERROR,
            "helper_protocol_invalid",
            "Target helper returned an unexpected response",
        )

    def _refusal(
        self,
        config: TargetAccessConfig,
        started_at: datetime,
        checks: list[PreflightCheck],
        name: str,
        category: str,
        message: str,
        check_started: float | None = None,
    ) -> PreflightReport:
        return self._failure(
            config,
            started_at,
            checks,
            name,
            PreflightOutcome.REFUSED,
            category,
            message,
            check_started,
        )

    def _failure(
        self,
        config: TargetAccessConfig,
        started_at: datetime,
        checks: list[PreflightCheck],
        name: str,
        outcome: PreflightOutcome,
        category: str,
        message: str,
        check_started: float | None = None,
    ) -> PreflightReport:
        checks.append(
            PreflightCheck(
                name=name,
                status=PreflightCheckStatus.FAIL,
                message=message,
                duration_ms=self._duration(check_started),
            )
        )
        current_index = CHECK_NAMES.index(name)
        for skipped in CHECK_NAMES[current_index + 1 :]:
            checks.append(
                PreflightCheck(
                    name=skipped,
                    status=PreflightCheckStatus.SKIP,
                    message="Skipped because a prerequisite failed",
                    duration_ms=0,
                )
            )
        return self._report(config, started_at, checks, outcome, category)

    def _pass(
        self,
        checks: list[PreflightCheck],
        name: str,
        message: str,
        check_started: float | None = None,
    ) -> None:
        checks.append(
            PreflightCheck(
                name=name,
                status=PreflightCheckStatus.PASS,
                message=message,
                duration_ms=self._duration(check_started),
            )
        )

    def _duration(self, started: float | None) -> int:
        if started is None:
            return 0
        return min(max(round((self._monotonic() - started) * 1000), 0), 60_000)

    def _report(
        self,
        config: TargetAccessConfig,
        started_at: datetime,
        checks: list[PreflightCheck],
        outcome: PreflightOutcome,
        category: str | None,
    ) -> PreflightReport:
        report = PreflightReport(
            outcome=outcome,
            expected_target_id=config.target_id,
            target_label=f"{config.target_host}:{config.target_port}",
            started_at=started_at,
            completed_at=self._now(),
            checks=tuple(checks),
            category=category,
        )
        log_event(
            self._logger,
            logging.INFO if outcome is PreflightOutcome.PASS else logging.WARNING,
            LogEvent.PREFLIGHT_COMPLETED,
            "Target preflight completed",
            fields={
                "expected_target_id": str(config.target_id),
                "outcome": outcome.value,
                "category": category,
            },
        )
        return report


def _helper_major(version: str) -> int:
    return int(version.split(".", maxsplit=1)[0])
