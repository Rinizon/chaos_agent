"""Tests for bounded, unauthenticated website observation."""

import asyncio
from pathlib import Path

import httpx
import pytest

from chaos_agent.adapters.http_observer import HttpxSiteObserver
from chaos_agent.application.observer import SiteFailure, SiteObservationError
from chaos_agent.config import Settings, TargetAccessConfig

TARGET_ID = "8d047f58-0dc7-4d61-a165-82b02edbc2c8"


def access_config(tmp_path: Path, **overrides: object) -> TargetAccessConfig:
    values: dict[str, object] = {
        "target_id": TARGET_ID,
        "target_host": "dev-web.internal",
        "site_health_url": "https://site.internal/health",
        "site_expected_content": "healthy",
        "ssh_private_key_path": tmp_path / "id_ed25519",
        "ssh_known_hosts_path": tmp_path / "known_hosts",
    }
    values.update(overrides)
    return Settings(**values, _env_file=None).require_target_access()


def test_observer_returns_bounded_status_latency_and_content_match(tmp_path: Path) -> None:
    captured: dict[str, str | None] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["authorization"] = request.headers.get("authorization")
        captured["cookie"] = request.headers.get("cookie")
        return httpx.Response(200, content=b"site is healthy")

    ticks = iter([10.0, 10.025])
    observation = asyncio.run(
        HttpxSiteObserver(
            transport=httpx.MockTransport(handler), monotonic=lambda: next(ticks)
        ).observe(access_config(tmp_path))
    )

    assert observation.status_code == 200
    assert observation.duration_ms == 25
    assert observation.content_matched is True
    assert captured == {
        "url": "https://site.internal/health",
        "authorization": None,
        "cookie": None,
    }


def test_observer_reports_content_mismatch_without_returning_body(tmp_path: Path) -> None:
    transport = httpx.MockTransport(lambda _: httpx.Response(200, content=b"not the marker"))

    observation = asyncio.run(
        HttpxSiteObserver(transport=transport).observe(access_config(tmp_path))
    )

    assert observation.content_matched is False
    assert "body" not in observation.model_dump()


@pytest.mark.parametrize(
    "response,category",
    [
        (
            httpx.Response(302, headers={"location": "https://elsewhere.invalid"}),
            SiteFailure.REDIRECT_REFUSED,
        ),
        (httpx.Response(200, content=b"x" * 2000), SiteFailure.RESPONSE_TOO_LARGE),
    ],
)
def test_observer_refuses_redirects_and_large_responses(
    tmp_path: Path, response: httpx.Response, category: SiteFailure
) -> None:
    config = access_config(tmp_path, site_max_response_bytes=1024)
    transport = httpx.MockTransport(lambda _: response)

    with pytest.raises(SiteObservationError) as captured:
        asyncio.run(HttpxSiteObserver(transport=transport).observe(config))

    assert captured.value.category is category
    assert str(captured.value) == category.value


@pytest.mark.parametrize(
    "error,category",
    [
        (httpx.ReadTimeout("synthetic timeout"), SiteFailure.TIMEOUT),
        (httpx.ConnectError("synthetic secret-bearing failure"), SiteFailure.CONNECTION_FAILED),
    ],
)
def test_observer_classifies_transport_failures_without_diagnostics(
    tmp_path: Path, error: httpx.HTTPError, category: SiteFailure
) -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        raise error

    with pytest.raises(SiteObservationError) as captured:
        asyncio.run(
            HttpxSiteObserver(transport=httpx.MockTransport(handler)).observe(
                access_config(tmp_path)
            )
        )

    assert captured.value.category is category
    assert "synthetic" not in str(captured.value)


def test_configuration_has_no_tls_disable_setting(tmp_path: Path) -> None:
    config = access_config(tmp_path)

    assert "verify" not in type(config).model_fields
    assert str(config.site_health_url).startswith("https://")


def test_total_request_deadline_bounds_slow_mock_transport(tmp_path: Path) -> None:
    async def slow_handler(_: httpx.Request) -> httpx.Response:
        await asyncio.sleep(0.1)
        return httpx.Response(200)

    config = access_config(tmp_path, site_timeout_seconds="0.01")
    with pytest.raises(SiteObservationError) as captured:
        asyncio.run(HttpxSiteObserver(transport=httpx.MockTransport(slow_handler)).observe(config))

    assert captured.value.category is SiteFailure.TIMEOUT
