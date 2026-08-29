"""Application-facing external website observation boundary."""

from enum import StrEnum
from typing import Protocol

from chaos_agent.config import TargetAccessConfig
from chaos_agent.domain.preflight import SiteObservation


class SiteFailure(StrEnum):
    """Stable website observation failure categories."""

    TIMEOUT = "website_timeout"
    CONNECTION_FAILED = "website_connection_failed"
    REDIRECT_REFUSED = "website_redirect_refused"
    RESPONSE_TOO_LARGE = "website_response_too_large"


class SiteObservationError(RuntimeError):
    """A safe website failure without URL, body, or transport diagnostics."""

    def __init__(self, category: SiteFailure) -> None:
        self.category = category
        super().__init__(category.value)


class SiteObserver(Protocol):
    """Perform one bounded, unauthenticated external site observation."""

    async def observe(self, config: TargetAccessConfig) -> SiteObservation: ...
