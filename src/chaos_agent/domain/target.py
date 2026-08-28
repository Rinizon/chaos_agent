"""Strict target identity and helper protocol contracts."""

from dataclasses import dataclass
from enum import StrEnum
from typing import Annotated, Literal
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StrictFloat,
    StrictInt,
    StrictStr,
    StringConstraints,
)

HELPER_PROTOCOL_VERSION = 1
SUPPORTED_HELPER_MAJOR = 0
VersionString = Annotated[
    StrictStr,
    StringConstraints(pattern=r"^[0-9]+\.[0-9]+\.[0-9]+$", max_length=32),
]


class ApacheService(StrEnum):
    """Apache service units supported by the initial target contract."""

    APACHE2 = "apache2.service"
    HTTPD = "httpd.service"


class RemoteOperation(StrEnum):
    """Closed set of read-only Phase 2 helper operations."""

    VERSION = "version"
    IDENTITY = "identity"
    PREFLIGHT = "preflight"


class ContractModel(BaseModel):
    """Base for strict, immutable helper protocol models."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class TargetMarker(ContractModel):
    """Root-owned development-target identity marker."""

    schema_version: Literal[1]
    target_id: UUID
    environment: Literal["development"]
    role: Literal["web"]
    apache_service: ApacheService


class HelperEnvelope(ContractModel):
    """Fields common to every successful helper response."""

    protocol_version: Literal[1]
    helper_version: VersionString


class HelperVersionResponse(HelperEnvelope):
    """Response from the fixed helper version operation."""

    operation: Literal["version"]


class IdentityResponse(HelperEnvelope):
    """Identity values reported by the root-owned target helper."""

    operation: Literal["identity"]
    marker_schema_version: Literal[1]
    target_id: UUID
    environment: StrictStr = Field(min_length=1, max_length=32)
    role: StrictStr = Field(min_length=1, max_length=32)
    apache_service: StrictStr = Field(min_length=1, max_length=64)


class ApacheFacts(ContractModel):
    """Read-only Apache facts returned by helper preflight."""

    service: StrictStr = Field(min_length=1, max_length=64)
    installed: StrictBool
    active: StrictBool


class ResourceFacts(ContractModel):
    """Bounded read-only host resource facts."""

    root_free_bytes: StrictInt = Field(ge=0, le=2**63 - 1)
    memory_available_bytes: StrictInt = Field(ge=0, le=2**63 - 1)
    logical_cpu_count: StrictInt = Field(ge=1, le=1_048_576)
    load_1m: StrictFloat = Field(ge=0, le=1_000_000, allow_inf_nan=False)


class PreflightResponse(HelperEnvelope):
    """Strict response from the root-owned read-only preflight helper."""

    operation: Literal["preflight"]
    marker_schema_version: Literal[1]
    target_id: UUID
    environment: StrictStr = Field(min_length=1, max_length=32)
    role: StrictStr = Field(min_length=1, max_length=32)
    apache_service: StrictStr = Field(min_length=1, max_length=64)
    effective_uid: Literal[0]
    apache: ApacheFacts
    resources: ResourceFacts


class IdentityRefusalCode(StrEnum):
    """Safe reasons for refusing helper identity data."""

    HELPER_VERSION_UNSUPPORTED = "helper_version_unsupported"
    TARGET_ID_MISMATCH = "target_id_mismatch"
    PRODUCTION_REFUSED = "production_refused"
    ENVIRONMENT_UNKNOWN = "environment_unknown"
    ROLE_MISMATCH = "role_mismatch"
    APACHE_SERVICE_MISMATCH = "apache_service_mismatch"


class TargetIdentityRefused(ValueError):
    """A safe target refusal with no raw helper payload."""

    def __init__(self, code: IdentityRefusalCode) -> None:
        self.code = code
        super().__init__(code.value)


@dataclass(frozen=True)
class TargetExpectation:
    """Expected application-level identity for one configured dev target."""

    target_id: UUID
    apache_service: ApacheService


def verify_target_identity(
    expectation: TargetExpectation,
    response: IdentityResponse | PreflightResponse,
) -> None:
    """Refuse any helper response that is not the exact expected dev web target."""
    helper_major = int(response.helper_version.split(".", maxsplit=1)[0])
    if helper_major != SUPPORTED_HELPER_MAJOR:
        raise TargetIdentityRefused(IdentityRefusalCode.HELPER_VERSION_UNSUPPORTED)
    if response.environment == "production":
        raise TargetIdentityRefused(IdentityRefusalCode.PRODUCTION_REFUSED)
    if response.environment != "development":
        raise TargetIdentityRefused(IdentityRefusalCode.ENVIRONMENT_UNKNOWN)
    if response.role != "web":
        raise TargetIdentityRefused(IdentityRefusalCode.ROLE_MISMATCH)
    if response.target_id != expectation.target_id:
        raise TargetIdentityRefused(IdentityRefusalCode.TARGET_ID_MISMATCH)
    if response.apache_service != expectation.apache_service.value:
        raise TargetIdentityRefused(IdentityRefusalCode.APACHE_SERVICE_MISMATCH)
