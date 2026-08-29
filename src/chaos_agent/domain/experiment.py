"""Pure domain contracts for experiment lifecycle and safety policy."""

from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any, Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, StrictInt, StrictStr, field_validator

EXPERIMENT_ID_PREFIX = "exp_"
DEFAULT_DURATION_SECONDS = 300
HARD_MAX_DURATION_SECONDS = 3600


class ExperimentId(str):
    """Opaque experiment identifier with a stable CLI/storage format."""

    @classmethod
    def new(cls) -> "ExperimentId":
        return cls(f"{EXPERIMENT_ID_PREFIX}{uuid4().hex}")

    @classmethod
    def validate(cls, value: str) -> "ExperimentId":
        if len(value) != 36 or not value.startswith(EXPERIMENT_ID_PREFIX):
            raise ValueError("invalid experiment id")
        if any(character not in "0123456789abcdef" for character in value[4:]):
            raise ValueError("invalid experiment id")
        return cls(value)


class ExperimentState(StrEnum):
    PLANNED = "planned"
    PREFLIGHT = "preflight"
    INJECTING = "injecting"
    ACTIVE = "active"
    CANCELLATION_REQUESTED = "cancellation_requested"
    EXPIRED = "expired"
    CLEANING_UP = "cleaning_up"
    VERIFYING = "verifying"
    PASSED = "passed"
    CANCELLED = "cancelled"
    FAILED = "failed"
    CLEANUP_FAILED = "cleanup_failed"
    OPERATOR_ATTENTION = "operator_attention"


TERMINAL_STATES = frozenset(
    {
        ExperimentState.PASSED,
        ExperimentState.CANCELLED,
        ExperimentState.FAILED,
        ExperimentState.OPERATOR_ATTENTION,
    }
)
ALLOWED_TRANSITIONS: dict[ExperimentState, frozenset[ExperimentState]] = {
    ExperimentState.PLANNED: frozenset({ExperimentState.PREFLIGHT, ExperimentState.CANCELLED}),
    ExperimentState.PREFLIGHT: frozenset(
        {ExperimentState.INJECTING, ExperimentState.FAILED, ExperimentState.CANCELLED}
    ),
    ExperimentState.INJECTING: frozenset({ExperimentState.ACTIVE, ExperimentState.CLEANING_UP}),
    ExperimentState.ACTIVE: frozenset(
        {
            ExperimentState.EXPIRED,
            ExperimentState.CANCELLATION_REQUESTED,
            ExperimentState.CLEANING_UP,
        }
    ),
    ExperimentState.CANCELLATION_REQUESTED: frozenset({ExperimentState.CLEANING_UP}),
    ExperimentState.EXPIRED: frozenset({ExperimentState.CLEANING_UP}),
    ExperimentState.CLEANING_UP: frozenset(
        {ExperimentState.VERIFYING, ExperimentState.CLEANUP_FAILED}
    ),
    ExperimentState.CLEANUP_FAILED: frozenset(
        {ExperimentState.CLEANING_UP, ExperimentState.OPERATOR_ATTENTION}
    ),
    ExperimentState.VERIFYING: frozenset(
        {
            ExperimentState.PASSED,
            ExperimentState.CANCELLED,
            ExperimentState.FAILED,
            ExperimentState.OPERATOR_ATTENTION,
        }
    ),
}


class TransitionReason(StrEnum):
    SCHEDULED = "scheduled"
    PREFLIGHT_PASSED = "preflight_passed"
    PREFLIGHT_REFUSED = "preflight_refused"
    INJECTION_VERIFIED = "injection_verified"
    INJECTION_UNCERTAIN = "injection_uncertain"
    EXPIRED = "expired"
    ABORT_REQUESTED = "abort_requested"
    CLEANUP_SUCCEEDED = "cleanup_succeeded"
    CLEANUP_FAILED = "cleanup_failed"
    VERIFICATION_PASSED = "verification_passed"
    VERIFICATION_FAILED = "verification_failed"


class ExperimentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    target_id: UUID
    target_label: StrictStr = Field(min_length=1, max_length=255)
    scenario_name: StrictStr = Field(pattern=r"^[a-z][a-z0-9-]{1,63}$")
    scenario_version: StrictStr = Field(pattern=r"^[0-9]+\.[0-9]+\.[0-9]+$")
    parameters: dict[str, Any] = Field(default_factory=dict)
    requested_duration_seconds: StrictInt = Field(
        default=DEFAULT_DURATION_SECONDS, ge=1, le=HARD_MAX_DURATION_SECONDS
    )
    initiator: StrictStr = Field(min_length=1, max_length=255)

    @field_validator("parameters")
    @classmethod
    def copy_parameters(cls, value: dict[str, Any]) -> dict[str, Any]:
        return dict(value)


class ExperimentTiming(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    created_at: datetime
    expires_at: datetime

    @field_validator("created_at", "expires_at")
    @classmethod
    def utc_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("timestamps must include a timezone")
        return value.astimezone(UTC)


class SanitizedEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    status: Literal["ok", "failed", "uncertain"]
    message: StrictStr = Field(min_length=1, max_length=512)
    details: dict[str, StrictStr] = Field(default_factory=dict)


class StateTransition(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    from_state: ExperimentState
    to_state: ExperimentState
    occurred_at: datetime
    reason: TransitionReason
    actor: StrictStr = Field(min_length=1, max_length=255)
    revision: StrictInt = Field(ge=0)


def validate_transition(current: ExperimentState, target: ExperimentState) -> None:
    """Enforce the sole lifecycle graph; terminal states cannot mutate."""
    if target not in ALLOWED_TRANSITIONS.get(current, frozenset()):
        raise ValueError(f"transition {current.value} -> {target.value} is not allowed")


def calculate_expiry(created_at: datetime, duration_seconds: int) -> datetime:
    if duration_seconds < 1 or duration_seconds > HARD_MAX_DURATION_SECONDS:
        raise ValueError("duration exceeds experiment safety limits")
    if created_at.tzinfo is None or created_at.utcoffset() is None:
        raise ValueError("created_at must include a timezone")
    return created_at.astimezone(UTC) + timedelta(seconds=duration_seconds)
