"""Strict, sanitized event contract for independent remedy systems."""

from datetime import UTC, datetime
from typing import Any, Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, StrictStr

EventType = Literal[
    "experiment.scheduled", "experiment.preflight_completed", "experiment.injection_verified",
    "experiment.observation", "experiment.expired", "experiment.cancellation_requested",
    "experiment.cleanup_completed", "experiment.finalized", "integration.delivery_failed",
]


class IntegrationEvent(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    schema_version: Literal[1] = 1
    event_id: UUID = Field(default_factory=uuid4)
    event_type: EventType
    event_version: StrictStr = "1.0.0"
    experiment_id: StrictStr = Field(pattern=r"^exp_[0-9a-f]{32}$")
    scenario_name: StrictStr = Field(pattern=r"^[a-z][a-z0-9-]{1,63}$")
    scenario_version: StrictStr = Field(pattern=r"^[0-9]+\.[0-9]+\.[0-9]+$")
    target_ref: StrictStr = Field(min_length=1, max_length=128)
    occurred_at: datetime
    correlation_id: StrictStr = Field(min_length=1, max_length=128)
    actor: StrictStr = Field(min_length=1, max_length=128)
    payload: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def create(cls, **values: Any) -> "IntegrationEvent":
        values.setdefault("occurred_at", datetime.now(UTC))
        return cls(**values)
