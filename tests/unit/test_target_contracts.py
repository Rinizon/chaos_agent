"""Tests for strict target identity and helper response contracts."""

import json
from uuid import UUID

import pytest
from pydantic import ValidationError

from chaos_agent.domain.target import (
    ApacheFacts,
    ApacheService,
    IdentityRefusalCode,
    IdentityResponse,
    PreflightResponse,
    ResourceFacts,
    TargetExpectation,
    TargetIdentityRefused,
    TargetMarker,
    verify_target_identity,
)

TARGET_ID = UUID("8d047f58-0dc7-4d61-a165-82b02edbc2c8")


def identity_values(**overrides: object) -> dict[str, object]:
    values: dict[str, object] = {
        "protocol_version": 1,
        "helper_version": "0.1.0",
        "operation": "identity",
        "marker_schema_version": 1,
        "target_id": TARGET_ID,
        "environment": "development",
        "role": "web",
        "apache_service": "apache2.service",
    }
    values.update(overrides)
    return values


def test_target_marker_accepts_only_development_web_contract() -> None:
    marker = TargetMarker.model_validate(
        {
            "schema_version": 1,
            "target_id": TARGET_ID,
            "environment": "development",
            "role": "web",
            "apache_service": "apache2.service",
        }
    )

    assert marker.target_id == TARGET_ID
    assert marker.apache_service is ApacheService.APACHE2


@pytest.mark.parametrize(
    "override",
    [
        {"environment": "production"},
        {"environment": "unknown"},
        {"role": "database"},
        {"apache_service": "nginx.service"},
        {"schema_version": 2},
        {"extra": "forbidden"},
    ],
)
def test_target_marker_rejects_unsupported_or_unknown_values(override: dict[str, object]) -> None:
    values: dict[str, object] = {
        "schema_version": 1,
        "target_id": TARGET_ID,
        "environment": "development",
        "role": "web",
        "apache_service": "apache2.service",
    }
    values.update(override)

    with pytest.raises(ValidationError):
        TargetMarker.model_validate(values)


def test_identity_response_rejects_unknown_fields_and_coerced_protocol_values() -> None:
    with pytest.raises(ValidationError):
        IdentityResponse.model_validate({**identity_values(), "unexpected": True})
    with pytest.raises(ValidationError):
        IdentityResponse.model_validate({**identity_values(), "protocol_version": "1"})


def test_preflight_response_parses_strict_nested_facts() -> None:
    response = PreflightResponse(
        protocol_version=1,
        helper_version="0.1.0",
        operation="preflight",
        marker_schema_version=1,
        target_id=TARGET_ID,
        environment="development",
        role="web",
        apache_service="apache2.service",
        effective_uid=0,
        apache=ApacheFacts(service="apache2.service", installed=True, active=True),
        resources=ResourceFacts(
            root_free_bytes=5_368_709_120,
            memory_available_bytes=1_073_741_824,
            logical_cpu_count=2,
            load_1m=0.25,
        ),
    )

    assert response.resources.logical_cpu_count == 2
    assert response.effective_uid == 0


@pytest.mark.parametrize(
    "field,value",
    [
        ("root_free_bytes", -1),
        ("memory_available_bytes", -1),
        ("logical_cpu_count", 0),
        ("load_1m", float("inf")),
        ("load_1m", "0.25"),
    ],
)
def test_resource_facts_reject_invalid_or_coerced_values(field: str, value: object) -> None:
    values: dict[str, object] = {
        "root_free_bytes": 1,
        "memory_available_bytes": 1,
        "logical_cpu_count": 1,
        "load_1m": 0.25,
    }
    values[field] = value

    with pytest.raises(ValidationError):
        ResourceFacts.model_validate(values)


def test_identity_policy_accepts_exact_expected_target() -> None:
    response = IdentityResponse.model_validate(identity_values())

    verify_target_identity(TargetExpectation(TARGET_ID, ApacheService.APACHE2), response)


@pytest.mark.parametrize(
    "override,code",
    [
        ({"helper_version": "1.0.0"}, IdentityRefusalCode.HELPER_VERSION_UNSUPPORTED),
        ({"environment": "production"}, IdentityRefusalCode.PRODUCTION_REFUSED),
        ({"environment": "staging"}, IdentityRefusalCode.ENVIRONMENT_UNKNOWN),
        ({"role": "database"}, IdentityRefusalCode.ROLE_MISMATCH),
        (
            {"target_id": UUID("d30ff812-eb0d-48d8-90fe-558c614293b3")},
            IdentityRefusalCode.TARGET_ID_MISMATCH,
        ),
        ({"apache_service": "httpd.service"}, IdentityRefusalCode.APACHE_SERVICE_MISMATCH),
    ],
)
def test_identity_policy_refuses_every_mismatch(
    override: dict[str, object], code: IdentityRefusalCode
) -> None:
    response = IdentityResponse.model_validate(identity_values(**override))

    with pytest.raises(TargetIdentityRefused) as captured:
        verify_target_identity(TargetExpectation(TARGET_ID, ApacheService.APACHE2), response)

    assert captured.value.code is code
    assert json.dumps(response.model_dump(mode="json")) not in str(captured.value)
