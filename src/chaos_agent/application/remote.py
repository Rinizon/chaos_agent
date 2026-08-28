"""Application-facing remote execution boundary."""

from typing import Protocol

from chaos_agent.config import TargetAccessConfig
from chaos_agent.domain.target import (
    HelperVersionResponse,
    IdentityResponse,
    PreflightResponse,
    RemoteOperation,
)

RemoteResponse = HelperVersionResponse | IdentityResponse | PreflightResponse


class RemoteTransport(Protocol):
    """Execute only a closed helper operation against a configured target."""

    async def execute(
        self,
        config: TargetAccessConfig,
        operation: RemoteOperation,
    ) -> RemoteResponse: ...
