"""Application-facing remote execution boundary."""

from enum import StrEnum
from typing import Protocol

from chaos_agent.config import TargetAccessConfig
from chaos_agent.domain.target import (
    HelperVersionResponse,
    IdentityResponse,
    PreflightResponse,
    RemoteOperation,
)

RemoteResponse = HelperVersionResponse | IdentityResponse | PreflightResponse


class TransportFailure(StrEnum):
    """Stable, secret-safe remote transport failure categories."""

    SSH_EXECUTABLE_MISSING = "ssh_executable_missing"
    SSH_CLIENT_UNSUPPORTED = "ssh_client_unsupported"
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


class RemoteTransport(Protocol):
    """Execute only a closed helper operation against a configured target."""

    async def check_client(self) -> str:
        """Return a sanitized supported local OpenSSH version."""
        ...

    async def execute(
        self,
        config: TargetAccessConfig,
        operation: RemoteOperation,
    ) -> RemoteResponse: ...
