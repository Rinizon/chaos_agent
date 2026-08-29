"""Bounded HTTPX website observer."""

import asyncio
import time
from collections.abc import Callable

import httpx

from chaos_agent.application.observer import SiteFailure, SiteObservationError
from chaos_agent.config import TargetAccessConfig
from chaos_agent.domain.preflight import SiteObservation


class HttpxSiteObserver:
    """Make one redirect-free, credential-free, size-bounded GET request."""

    def __init__(
        self,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        self._transport = transport
        self._monotonic = monotonic

    async def observe(self, config: TargetAccessConfig) -> SiteObservation:
        timeout_seconds = float(config.site_timeout_seconds)
        timeout = httpx.Timeout(timeout_seconds)
        verify: bool | str = (
            str(config.site_ca_bundle_path) if config.site_ca_bundle_path is not None else True
        )
        started = self._monotonic()
        try:
            async with asyncio.timeout(timeout_seconds):
                async with (
                    httpx.AsyncClient(
                        follow_redirects=False,
                        timeout=timeout,
                        verify=verify,
                        transport=self._transport,
                        trust_env=False,
                        headers={"Accept": "text/html,application/xhtml+xml"},
                    ) as client,
                    client.stream("GET", str(config.site_health_url)) as response,
                ):
                    if response.is_redirect:
                        raise SiteObservationError(SiteFailure.REDIRECT_REFUSED)
                    body = bytearray()
                    async for chunk in response.aiter_bytes():
                        body.extend(chunk)
                        if len(body) > config.site_max_response_bytes:
                            raise SiteObservationError(SiteFailure.RESPONSE_TOO_LARGE)
        except (TimeoutError, httpx.TimeoutException) as error:
            raise SiteObservationError(SiteFailure.TIMEOUT) from error
        except (OSError, httpx.HTTPError) as error:
            raise SiteObservationError(SiteFailure.CONNECTION_FAILED) from error

        duration_ms = min(max(round((self._monotonic() - started) * 1000), 0), 60_000)
        expected = config.site_expected_content
        content_matched = expected is None or expected.encode("utf-8") in body
        return SiteObservation(
            status_code=response.status_code,
            duration_ms=duration_ms,
            content_matched=content_matched,
        )
