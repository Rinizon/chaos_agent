"""Tests for ordered, short-circuiting preflight orchestration."""

import asyncio
import io
import logging
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from chaos_agent.application.observer import SiteFailure, SiteObservationError
from chaos_agent.application.preflight import CHECK_NAMES, PreflightService
from chaos_agent.application.remote import (
    RemoteResponse,
    RemoteTransportError,
    TransportFailure,
)
from chaos_agent.config import Settings, TargetAccessConfig
from chaos_agent.domain.preflight import (
    PreflightCheckStatus,
    PreflightOutcome,
    SiteObservation,
)
from chaos_agent.domain.target import (
    ApacheFacts,
    HelperVersionResponse,
    IdentityResponse,
    PreflightResponse,
    RemoteOperation,
    ResourceFacts,
)
from chaos_agent.logging import JsonFormatter

TARGET_ID = "8d047f58-0dc7-4d61-a165-82b02edbc2c8"


def access_config(tmp_path: Path, **overrides: object) -> TargetAccessConfig:
    key = tmp_path / "id_ed25519"
    known_hosts = tmp_path / "known_hosts"
    key.write_text("synthetic-key", encoding="utf-8")
    known_hosts.write_text("synthetic-host-key", encoding="utf-8")
    key.chmod(0o600)
    known_hosts.chmod(0o644)
    values: dict[str, object] = {
        "target_id": TARGET_ID,
        "target_host": "dev-web.internal",
        "site_health_url": "https://site.internal/health",
        "ssh_private_key_path": key,
        "ssh_known_hosts_path": known_hosts,
    }
    values.update(overrides)
    return Settings(**values, _env_file=None).require_target_access()


def responses(**preflight_changes: object) -> dict[RemoteOperation, RemoteResponse]:
    common = {
        "protocol_version": 1,
        "helper_version": "0.1.0",
    }
    identity_values = {
        **common,
        "operation": "identity",
        "marker_schema_version": 1,
        "target_id": TARGET_ID,
        "environment": "development",
        "role": "web",
        "apache_service": "apache2.service",
    }
    preflight_values: dict[str, object] = {
        **common,
        "operation": "preflight",
        "marker_schema_version": 1,
        "target_id": TARGET_ID,
        "environment": "development",
        "role": "web",
        "apache_service": "apache2.service",
        "effective_uid": 0,
        "apache": ApacheFacts(service="apache2.service", installed=True, active=True),
        "resources": ResourceFacts(
            root_free_bytes=2 * 1024**3,
            memory_available_bytes=1024**3,
            logical_cpu_count=2,
            load_1m=0.5,
        ),
    }
    preflight_values.update(preflight_changes)
    return {
        RemoteOperation.VERSION: HelperVersionResponse(**common, operation="version"),
        RemoteOperation.IDENTITY: IdentityResponse(**identity_values),
        RemoteOperation.PREFLIGHT: PreflightResponse(**preflight_values),
    }


class FakeRemote:
    def __init__(self, configured: dict[RemoteOperation, RemoteResponse]) -> None:
        self.responses = configured
        self.calls: list[str] = []
        self.client_error: RemoteTransportError | None = None
        self.operation_error: tuple[RemoteOperation, RemoteTransportError] | None = None

    async def check_client(self) -> str:
        self.calls.append("client")
        if self.client_error is not None:
            raise self.client_error
        return "OpenSSH_9.9"

    async def execute(self, _: TargetAccessConfig, operation: RemoteOperation) -> RemoteResponse:
        self.calls.append(operation.value)
        if self.operation_error is not None and self.operation_error[0] is operation:
            raise self.operation_error[1]
        return self.responses[operation]


class FakeObserver:
    def __init__(self) -> None:
        self.calls = 0
        self.result = SiteObservation(status_code=200, duration_ms=5, content_matched=True)
        self.error: SiteObservationError | None = None

    async def observe(self, _: TargetAccessConfig) -> SiteObservation:
        self.calls += 1
        if self.error is not None:
            raise self.error
        return self.result


def run_service(config: TargetAccessConfig, remote: FakeRemote, observer: FakeObserver):
    timestamps = iter(
        [
            datetime(2026, 8, 28, tzinfo=UTC),
            datetime(2026, 8, 28, tzinfo=UTC) + timedelta(seconds=1),
        ]
    )
    return asyncio.run(PreflightService(remote, observer, now=lambda: next(timestamps)).run(config))


def test_preflight_passes_only_after_every_ordered_check(tmp_path: Path) -> None:
    remote = FakeRemote(responses())
    observer = FakeObserver()

    report = run_service(access_config(tmp_path), remote, observer)

    assert report.outcome is PreflightOutcome.PASS
    assert report.category is None
    assert [check.name for check in report.checks] == list(CHECK_NAMES)
    assert all(check.status is PreflightCheckStatus.PASS for check in report.checks)
    assert remote.calls == ["client", "version", "identity", "preflight"]
    assert observer.calls == 1


def test_identity_refusal_prevents_preflight_and_website_checks(tmp_path: Path) -> None:
    configured = responses()
    configured[RemoteOperation.IDENTITY] = configured[RemoteOperation.IDENTITY].model_copy(
        update={"environment": "production"}
    )
    remote = FakeRemote(configured)
    observer = FakeObserver()

    report = run_service(access_config(tmp_path), remote, observer)

    assert report.outcome is PreflightOutcome.REFUSED
    assert report.category == "production_refused"
    assert remote.calls == ["client", "version", "identity"]
    assert observer.calls == 0
    assert report.checks[5].status is PreflightCheckStatus.SKIP


def test_transport_failure_is_error_and_skips_dependents(tmp_path: Path) -> None:
    remote = FakeRemote(responses())
    remote.operation_error = (
        RemoteOperation.VERSION,
        RemoteTransportError(TransportFailure.AUTHENTICATION_FAILED),
    )
    observer = FakeObserver()

    report = run_service(access_config(tmp_path), remote, observer)

    assert report.outcome is PreflightOutcome.ERROR
    assert report.category == "authentication_failed"
    assert observer.calls == 0
    assert report.checks[-1].status is PreflightCheckStatus.SKIP


def test_unsafe_local_access_file_stops_before_remote_helper(tmp_path: Path) -> None:
    config = access_config(tmp_path)
    config.ssh_private_key_path.unlink()
    remote = FakeRemote(responses())

    report = run_service(config, remote, FakeObserver())

    assert report.outcome is PreflightOutcome.ERROR
    assert report.category == "ssh_private_key_path_missing"
    assert remote.calls == ["client"]


def test_noninteractive_sudo_refusal_is_a_safety_refusal(tmp_path: Path) -> None:
    remote = FakeRemote(responses())
    remote.operation_error = (
        RemoteOperation.PREFLIGHT,
        RemoteTransportError(TransportFailure.REMOTE_PRIVILEGE_REFUSED),
    )

    report = run_service(access_config(tmp_path), remote, FakeObserver())

    assert report.outcome is PreflightOutcome.REFUSED
    assert report.category == "remote_privilege_refused"


def test_unsupported_helper_version_refuses_before_identity(tmp_path: Path) -> None:
    configured = responses()
    configured[RemoteOperation.VERSION] = HelperVersionResponse(
        protocol_version=1,
        helper_version="1.0.0",
        operation="version",
    )
    remote = FakeRemote(configured)

    report = run_service(access_config(tmp_path), remote, FakeObserver())

    assert report.outcome is PreflightOutcome.REFUSED
    assert report.category == "helper_version_unsupported"
    assert remote.calls == ["client", "version"]


def test_identity_change_between_operations_is_refused(tmp_path: Path) -> None:
    configured = responses()
    configured[RemoteOperation.PREFLIGHT] = configured[RemoteOperation.PREFLIGHT].model_copy(
        update={"target_id": "3d047f58-0dc7-4d61-a165-82b02edbc2c8"}
    )
    remote = FakeRemote(configured)
    observer = FakeObserver()

    report = run_service(access_config(tmp_path), remote, observer)

    assert report.outcome is PreflightOutcome.REFUSED
    assert report.category == "target_id_mismatch"
    assert remote.calls == ["client", "version", "identity", "preflight"]
    assert observer.calls == 0


@pytest.mark.parametrize(
    "changes,category,failed_check",
    [
        (
            {"apache": ApacheFacts(service="apache2.service", installed=True, active=False)},
            "apache_unhealthy",
            "apache",
        ),
        (
            {
                "resources": ResourceFacts(
                    root_free_bytes=1,
                    memory_available_bytes=1024**3,
                    logical_cpu_count=2,
                    load_1m=0.5,
                )
            },
            "root_space_reserve_low",
            "root_space",
        ),
        (
            {
                "resources": ResourceFacts(
                    root_free_bytes=2 * 1024**3,
                    memory_available_bytes=1,
                    logical_cpu_count=2,
                    load_1m=0.5,
                )
            },
            "memory_reserve_low",
            "memory",
        ),
        (
            {
                "resources": ResourceFacts(
                    root_free_bytes=2 * 1024**3,
                    memory_available_bytes=1024**3,
                    logical_cpu_count=1,
                    load_1m=2.0,
                )
            },
            "load_above_limit",
            "load",
        ),
    ],
)
def test_unhealthy_target_baselines_refuse_without_observation(
    tmp_path: Path, changes: dict[str, object], category: str, failed_check: str
) -> None:
    remote = FakeRemote(responses(**changes))
    observer = FakeObserver()

    report = run_service(access_config(tmp_path), remote, observer)

    assert report.outcome is PreflightOutcome.REFUSED
    assert report.category == category
    assert (
        next(check for check in report.checks if check.name == failed_check).status
        is PreflightCheckStatus.FAIL
    )
    assert observer.calls == 0


def test_website_success_cannot_override_target_failure(tmp_path: Path) -> None:
    remote = FakeRemote(
        responses(apache=ApacheFacts(service="apache2.service", installed=False, active=False))
    )
    observer = FakeObserver()

    report = run_service(access_config(tmp_path), remote, observer)

    assert report.category == "apache_unhealthy"
    assert observer.calls == 0


@pytest.mark.parametrize(
    "result,error,category",
    [
        (
            SiteObservation(status_code=503, duration_ms=1, content_matched=True),
            None,
            "website_status_mismatch",
        ),
        (
            SiteObservation(status_code=200, duration_ms=1, content_matched=False),
            None,
            "website_content_mismatch",
        ),
        (None, SiteObservationError(SiteFailure.TIMEOUT), "website_timeout"),
    ],
)
def test_website_failures_refuse(
    tmp_path: Path,
    result: SiteObservation | None,
    error: SiteObservationError | None,
    category: str,
) -> None:
    remote = FakeRemote(responses())
    observer = FakeObserver()
    if result is not None:
        observer.result = result
    observer.error = error

    report = run_service(access_config(tmp_path), remote, observer)

    assert report.outcome is PreflightOutcome.REFUSED
    assert report.category == category


def test_reports_do_not_contain_remote_payload_or_secret_paths(tmp_path: Path) -> None:
    config = access_config(tmp_path)
    remote = FakeRemote(responses())
    remote.client_error = RemoteTransportError(TransportFailure.SSH_EXECUTABLE_MISSING)

    report = run_service(config, remote, FakeObserver())
    serialized = report.model_dump_json()

    assert str(config.ssh_private_key_path) not in serialized
    assert "synthetic-key" not in serialized
    assert "ssh_executable_missing" in serialized


def test_preflight_emits_one_sanitized_structured_outcome_log(tmp_path: Path) -> None:
    stream = io.StringIO()
    logger = logging.Logger("preflight-test")
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JsonFormatter())
    logger.addHandler(handler)
    config = access_config(tmp_path)
    timestamps = iter(
        [
            datetime(2026, 8, 28, tzinfo=UTC),
            datetime(2026, 8, 28, tzinfo=UTC) + timedelta(seconds=1),
        ]
    )

    report = asyncio.run(
        PreflightService(
            FakeRemote(responses()),
            FakeObserver(),
            now=lambda: next(timestamps),
            logger=logger,
        ).run(config)
    )
    logged = stream.getvalue()

    assert report.outcome is PreflightOutcome.PASS
    assert '"event":"preflight.completed"' in logged
    assert '"outcome":"pass"' in logged
    assert str(config.target_id) in logged
    assert str(config.ssh_private_key_path) not in logged
    assert "synthetic-key" not in logged
