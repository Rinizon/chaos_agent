"""Bounded system OpenSSH adapter for the closed target-helper protocol."""

import asyncio
import json
import os
import signal
from collections.abc import Sequence
from contextlib import suppress
from enum import StrEnum
from typing import Final

from pydantic import ValidationError

from chaos_agent.application.remote import RemoteResponse
from chaos_agent.config import TargetAccessConfig, validate_access_files
from chaos_agent.domain.target import (
    HelperVersionResponse,
    IdentityResponse,
    PreflightResponse,
    RemoteOperation,
)

HELPER_PATH: Final = "/usr/local/libexec/chaos-agent/target-helper"
MAX_STREAM_BYTES: Final = 65_536
TERMINATION_GRACE_SECONDS: Final = 1.0


class TransportFailure(StrEnum):
    """Stable, secret-safe OpenSSH failure categories."""

    SSH_EXECUTABLE_MISSING = "ssh_executable_missing"
    CONNECTION_TIMEOUT = "connection_timeout"
    HOST_KEY_VERIFICATION_FAILED = "host_key_verification_failed"
    AUTHENTICATION_FAILED = "authentication_failed"
    CONNECTION_FAILED = "connection_failed"
    REMOTE_PRIVILEGE_REFUSED = "remote_privilege_refused"
    HELPER_NOT_FOUND = "helper_not_found"
    HELPER_PROTOCOL_INVALID = "helper_protocol_invalid"
    OUTPUT_LIMIT_EXCEEDED = "output_limit_exceeded"
    CANCELLED = "cancelled"


class RemoteTransportError(RuntimeError):
    """A classified failure that contains no raw command or remote output."""

    def __init__(self, category: TransportFailure) -> None:
        self.category = category
        super().__init__(category.value)


class _OutputLimitExceeded(Exception):
    pass


def build_ssh_argv(
    config: TargetAccessConfig,
    operation: RemoteOperation,
    *,
    executable: str = "ssh",
) -> tuple[str, ...]:
    """Build the complete fixed OpenSSH invocation without a shell command seam."""
    destination = f"{config.target_user}@{config.target_host}"
    remote_command = f"sudo -n {HELPER_PATH} {operation.value}"
    return (
        executable,
        "-F",
        "/dev/null",
        "-o",
        "BatchMode=yes",
        "-o",
        "IdentitiesOnly=yes",
        "-o",
        "StrictHostKeyChecking=yes",
        "-o",
        f"UserKnownHostsFile={config.ssh_known_hosts_path}",
        "-o",
        "GlobalKnownHostsFile=/dev/null",
        "-o",
        "PasswordAuthentication=no",
        "-o",
        "KbdInteractiveAuthentication=no",
        "-o",
        "ForwardAgent=no",
        "-o",
        "ClearAllForwardings=yes",
        "-o",
        "RequestTTY=no",
        "-o",
        "ConnectionAttempts=1",
        "-o",
        f"ConnectTimeout={config.ssh_connect_timeout_seconds}",
        "-o",
        "LogLevel=ERROR",
        "-p",
        str(config.target_port),
        "-i",
        str(config.ssh_private_key_path),
        "--",
        destination,
        remote_command,
    )


class OpenSshTransport:
    """Run a fixed helper operation with hard time and output bounds."""

    def __init__(self, *, executable: str = "ssh") -> None:
        self._executable = executable

    async def execute(
        self,
        config: TargetAccessConfig,
        operation: RemoteOperation,
    ) -> RemoteResponse:
        validate_access_files(config)
        argv = build_ssh_argv(config, operation, executable=self._executable)
        try:
            process = await asyncio.create_subprocess_exec(
                *argv,
                stdin=asyncio.subprocess.DEVNULL,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                start_new_session=True,
            )
        except FileNotFoundError as error:
            raise RemoteTransportError(TransportFailure.SSH_EXECUTABLE_MISSING) from error
        except OSError as error:
            raise RemoteTransportError(TransportFailure.CONNECTION_FAILED) from error

        assert process.stdout is not None
        assert process.stderr is not None
        stdout_task = asyncio.create_task(_read_bounded(process.stdout))
        stderr_task = asyncio.create_task(_read_bounded(process.stderr))
        wait_task = asyncio.create_task(process.wait())
        tasks: tuple[asyncio.Task[object], ...] = (stdout_task, stderr_task, wait_task)
        try:
            results = await asyncio.wait_for(
                asyncio.gather(wait_task, stdout_task, stderr_task),
                timeout=config.ssh_command_timeout_seconds,
            )
        except TimeoutError as error:
            await _stop_and_reap(process, tasks)
            raise RemoteTransportError(TransportFailure.CONNECTION_TIMEOUT) from error
        except _OutputLimitExceeded as error:
            await _stop_and_reap(process, tasks)
            raise RemoteTransportError(TransportFailure.OUTPUT_LIMIT_EXCEEDED) from error
        except asyncio.CancelledError as error:
            await _stop_and_reap(process, tasks)
            raise RemoteTransportError(TransportFailure.CANCELLED) from error

        return_code = results[0]
        stdout = results[1]
        stderr = results[2]
        if return_code != 0:
            raise RemoteTransportError(_classify_failure(stderr))
        return _decode_response(stdout, operation)


async def _read_bounded(stream: asyncio.StreamReader) -> bytes:
    output = bytearray()
    while chunk := await stream.read(8192):
        output.extend(chunk)
        if len(output) > MAX_STREAM_BYTES:
            raise _OutputLimitExceeded
    return bytes(output)


async def _stop_and_reap(
    process: asyncio.subprocess.Process,
    tasks: Sequence[asyncio.Task[object]],
) -> None:
    for task in tasks:
        task.cancel()
    if process.returncode is None:
        _signal_process_group(process, signal.SIGTERM)
    try:
        await asyncio.wait_for(process.wait(), timeout=TERMINATION_GRACE_SECONDS)
    except TimeoutError:
        if process.returncode is None:
            _signal_process_group(process, signal.SIGKILL)
        await process.wait()
    await asyncio.gather(*tasks, return_exceptions=True)


def _signal_process_group(
    process: asyncio.subprocess.Process, requested_signal: signal.Signals
) -> None:
    """Signal only the isolated process group created for this invocation."""
    with suppress(ProcessLookupError):
        os.killpg(process.pid, requested_signal)


def _classify_failure(stderr: bytes) -> TransportFailure:
    diagnostic = stderr[:4096].decode("utf-8", errors="replace").casefold()
    if "host key verification failed" in diagnostic or "remote host identification" in diagnostic:
        return TransportFailure.HOST_KEY_VERIFICATION_FAILED
    if "sudo" in diagnostic and ("password" in diagnostic or "not allowed" in diagnostic):
        return TransportFailure.REMOTE_PRIVILEGE_REFUSED
    if "permission denied" in diagnostic:
        return TransportFailure.AUTHENTICATION_FAILED
    if HELPER_PATH.casefold() in diagnostic and (
        "not found" in diagnostic or "no such file" in diagnostic
    ):
        return TransportFailure.HELPER_NOT_FOUND
    return TransportFailure.CONNECTION_FAILED


def _decode_response(stdout: bytes, operation: RemoteOperation) -> RemoteResponse:
    try:
        document = stdout.decode("utf-8")
        decoder = json.JSONDecoder()
        payload, end = decoder.raw_decode(document.lstrip())
        if document.lstrip()[end:].strip():
            raise ValueError("trailing data")
        if not isinstance(payload, dict):
            raise ValueError("response is not an object")
        if operation is RemoteOperation.VERSION:
            response: RemoteResponse = HelperVersionResponse.model_validate_json(
                document, strict=True
            )
        elif operation is RemoteOperation.IDENTITY:
            response = IdentityResponse.model_validate_json(document, strict=True)
        else:
            response = PreflightResponse.model_validate_json(document, strict=True)
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError, ValidationError) as error:
        raise RemoteTransportError(TransportFailure.HELPER_PROTOCOL_INVALID) from error
    return response
