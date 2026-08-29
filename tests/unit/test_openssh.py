"""Tests for the bounded, closed OpenSSH adapter."""

import asyncio
import json
import os
from pathlib import Path
from uuid import UUID

import pytest

from chaos_agent.adapters.openssh import (
    HELPER_PATH,
    MAX_STREAM_BYTES,
    OpenSshTransport,
    build_ssh_argv,
)
from chaos_agent.application.remote import RemoteTransportError, TransportFailure
from chaos_agent.config import Settings, TargetAccessConfig
from chaos_agent.domain.target import HelperVersionResponse, RemoteOperation

TARGET_ID = "8d047f58-0dc7-4d61-a165-82b02edbc2c8"


def access_config(tmp_path: Path, *, timeout: int = 3) -> TargetAccessConfig:
    key = tmp_path / "id_ed25519"
    known_hosts = tmp_path / "known_hosts"
    key.write_text("synthetic-key", encoding="utf-8")
    known_hosts.write_text("synthetic-host-key", encoding="utf-8")
    key.chmod(0o600)
    known_hosts.chmod(0o644)
    return Settings(
        target_id=TARGET_ID,
        target_host="dev-web.internal",
        site_health_url="https://dev-web.internal/health",
        ssh_private_key_path=key,
        ssh_known_hosts_path=known_hosts,
        ssh_connect_timeout_seconds=1,
        ssh_command_timeout_seconds=timeout,
        _env_file=None,
    ).require_target_access()


def fake_executable(tmp_path: Path, body: str) -> Path:
    executable = tmp_path / "fake-ssh"
    executable.write_text(f"#!/bin/sh\n{body}\n", encoding="utf-8")
    executable.chmod(0o755)
    return executable


def test_fixed_argv_disables_ssh_fallbacks_and_uses_closed_command(tmp_path: Path) -> None:
    config = access_config(tmp_path)

    argv = build_ssh_argv(config, RemoteOperation.IDENTITY)

    assert argv[0] == "ssh"
    assert argv[1:3] == ("-F", "/dev/null")
    assert "BatchMode=yes" in argv
    assert "IdentitiesOnly=yes" in argv
    assert "StrictHostKeyChecking=yes" in argv
    assert "GlobalKnownHostsFile=/dev/null" in argv
    assert "PasswordAuthentication=no" in argv
    assert "KbdInteractiveAuthentication=no" in argv
    assert "ForwardAgent=no" in argv
    assert "ClearAllForwardings=yes" in argv
    assert "RequestTTY=no" in argv
    assert argv[-3:] == (
        "--",
        "chaos-agent@dev-web.internal",
        f"sudo -n {HELPER_PATH} identity",
    )


def test_fake_executable_captures_exact_argv_and_returns_strict_model(tmp_path: Path) -> None:
    capture = tmp_path / "argv.json"
    response = json.dumps(
        {"protocol_version": 1, "helper_version": "0.1.0", "operation": "version"}
    )
    executable = fake_executable(
        tmp_path,
        f"printf '%s\\n' \"$@\" > {capture}\nprintf '%s' '{response}'",
    )

    result = asyncio.run(
        OpenSshTransport(executable=str(executable)).execute(
            access_config(tmp_path), RemoteOperation.VERSION
        )
    )

    assert isinstance(result, HelperVersionResponse)
    captured = capture.read_text(encoding="utf-8").splitlines()
    assert captured[-2:] == [
        "chaos-agent@dev-web.internal",
        f"sudo -n {HELPER_PATH} version",
    ]


@pytest.mark.parametrize(
    "reported,expected",
    [("OpenSSH_9.8p1 synthetic", "OpenSSH_9.8"), ("OpenSSH_8.0", "OpenSSH_8.0")],
)
def test_client_check_accepts_supported_openssh_versions(
    tmp_path: Path, reported: str, expected: str
) -> None:
    executable = fake_executable(tmp_path, f"printf '%s' '{reported}' >&2")

    result = asyncio.run(OpenSshTransport(executable=str(executable)).check_client())

    assert result == expected


@pytest.mark.parametrize("reported", ["not-openssh", "OpenSSH_7.9"])
def test_client_check_refuses_unknown_or_old_clients(tmp_path: Path, reported: str) -> None:
    executable = fake_executable(tmp_path, f"printf '%s' '{reported}' >&2")

    with pytest.raises(RemoteTransportError) as captured:
        asyncio.run(OpenSshTransport(executable=str(executable)).check_client())

    assert captured.value.category is TransportFailure.SSH_CLIENT_UNSUPPORTED


@pytest.mark.parametrize(
    "stderr,category",
    [
        ("Host key verification failed.", TransportFailure.HOST_KEY_VERIFICATION_FAILED),
        ("Permission denied (publickey).", TransportFailure.AUTHENTICATION_FAILED),
        ("sudo: a password is required", TransportFailure.REMOTE_PRIVILEGE_REFUSED),
        (f"{HELPER_PATH}: not found", TransportFailure.HELPER_NOT_FOUND),
        ("connection refused secret-key-material", TransportFailure.CONNECTION_FAILED),
    ],
)
def test_nonzero_exit_is_classified_without_exposing_stderr(
    tmp_path: Path, stderr: str, category: TransportFailure
) -> None:
    executable = fake_executable(tmp_path, f"printf '%s' '{stderr}' >&2\nexit 255")

    with pytest.raises(RemoteTransportError) as captured:
        asyncio.run(
            OpenSshTransport(executable=str(executable)).execute(
                access_config(tmp_path), RemoteOperation.VERSION
            )
        )

    assert captured.value.category is category
    assert str(captured.value) == category.value
    assert "secret-key-material" not in str(captured.value)


@pytest.mark.parametrize(
    "stdout",
    [
        "not-json",
        "{} trailing",
        "[]",
        '{"protocol_version":1,"helper_version":"0.1.0","operation":"identity"}',
        '{"protocol_version":1,"helper_version":"0.1.0","operation":"version","extra":1}',
    ],
)
def test_malformed_or_mismatched_protocol_is_refused(tmp_path: Path, stdout: str) -> None:
    executable = fake_executable(tmp_path, f"printf '%s' '{stdout}'")

    with pytest.raises(RemoteTransportError) as captured:
        asyncio.run(
            OpenSshTransport(executable=str(executable)).execute(
                access_config(tmp_path), RemoteOperation.VERSION
            )
        )

    assert captured.value.category is TransportFailure.HELPER_PROTOCOL_INVALID


@pytest.mark.parametrize("redirect", ["", ">&2"])
def test_output_limit_terminates_process(tmp_path: Path, redirect: str) -> None:
    pid_file = tmp_path / "pid"
    executable = fake_executable(
        tmp_path,
        f"printf '%s' $$ > {pid_file}\n"
        f"dd if=/dev/zero bs={MAX_STREAM_BYTES + 1} count=1 {redirect} 2>/dev/null\n"
        "sleep 10",
    )

    with pytest.raises(RemoteTransportError) as captured:
        asyncio.run(
            OpenSshTransport(executable=str(executable)).execute(
                access_config(tmp_path), RemoteOperation.VERSION
            )
        )

    assert captured.value.category is TransportFailure.OUTPUT_LIMIT_EXCEEDED
    with pytest.raises(ProcessLookupError):
        os.kill(int(pid_file.read_text(encoding="utf-8")), 0)


def test_hard_deadline_terminates_process(tmp_path: Path) -> None:
    pid_file = tmp_path / "pid"
    executable = fake_executable(tmp_path, f"printf '%s' $$ > {pid_file}\nsleep 10")

    with pytest.raises(RemoteTransportError) as captured:
        asyncio.run(
            OpenSshTransport(executable=str(executable)).execute(
                access_config(tmp_path, timeout=2), RemoteOperation.VERSION
            )
        )

    assert captured.value.category is TransportFailure.CONNECTION_TIMEOUT
    with pytest.raises(ProcessLookupError):
        os.kill(int(pid_file.read_text(encoding="utf-8")), 0)


def test_missing_executable_is_classified(tmp_path: Path) -> None:
    with pytest.raises(RemoteTransportError) as captured:
        asyncio.run(
            OpenSshTransport(executable=str(tmp_path / "missing")).execute(
                access_config(tmp_path), RemoteOperation.VERSION
            )
        )

    assert captured.value.category is TransportFailure.SSH_EXECUTABLE_MISSING


def test_cancelled_execution_terminates_process(tmp_path: Path) -> None:
    executable = fake_executable(tmp_path, "sleep 10")

    async def cancel_running_transport() -> None:
        task = asyncio.create_task(
            OpenSshTransport(executable=str(executable)).execute(
                access_config(tmp_path), RemoteOperation.VERSION
            )
        )
        await asyncio.sleep(0.05)
        task.cancel()
        with pytest.raises(RemoteTransportError) as captured:
            await task
        assert captured.value.category is TransportFailure.CANCELLED

    asyncio.run(cancel_running_transport())


def test_response_contains_expected_typed_uuid(tmp_path: Path) -> None:
    payload = json.dumps(
        {
            "protocol_version": 1,
            "helper_version": "0.1.0",
            "operation": "identity",
            "marker_schema_version": 1,
            "target_id": TARGET_ID,
            "environment": "development",
            "role": "web",
            "apache_service": "apache2.service",
        }
    )
    executable = fake_executable(tmp_path, f"printf '%s' '{payload}'")

    result = asyncio.run(
        OpenSshTransport(executable=str(executable)).execute(
            access_config(tmp_path), RemoteOperation.IDENTITY
        )
    )

    assert result.target_id == UUID(TARGET_ID)
