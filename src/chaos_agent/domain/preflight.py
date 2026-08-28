"""Stable domain contracts for Phase 2 preflight reporting."""

from datetime import datetime
from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StrictInt, StrictStr, model_validator


class PreflightCheckStatus(StrEnum):
    """Outcome of one ordered preflight check."""

    PASS = "pass"
    FAIL = "fail"
    SKIP = "skip"


class PreflightOutcome(StrEnum):
    """Aggregate preflight result."""

    PASS = "pass"
    REFUSED = "refused"
    ERROR = "error"


class PreflightCheck(BaseModel):
    """One sanitized, ordered preflight check result."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: StrictStr = Field(pattern=r"^[a-z][a-z0-9_]{1,63}$")
    status: PreflightCheckStatus
    message: StrictStr = Field(min_length=1, max_length=256)
    duration_ms: StrictInt = Field(ge=0, le=60_000)


class PreflightReport(BaseModel):
    """Versioned, sanitized report returned by the application service."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[1] = 1
    outcome: PreflightOutcome
    expected_target_id: UUID
    target_label: StrictStr = Field(min_length=1, max_length=255)
    started_at: datetime
    completed_at: datetime
    checks: tuple[PreflightCheck, ...] = Field(min_length=1, max_length=32)
    category: StrictStr | None = Field(
        default=None,
        pattern=r"^[a-z][a-z0-9_]{1,63}$",
    )

    @model_validator(mode="after")
    def validate_outcome(self) -> "PreflightReport":
        if self.started_at.tzinfo is None or self.completed_at.tzinfo is None:
            raise ValueError("preflight timestamps must include a timezone")
        if self.completed_at < self.started_at:
            raise ValueError("preflight completion must not precede its start")
        if self.outcome is PreflightOutcome.PASS:
            if self.category is not None:
                raise ValueError("passing preflight must not contain an error category")
            if any(check.status is not PreflightCheckStatus.PASS for check in self.checks):
                raise ValueError("passing preflight requires every check to pass")
        elif self.category is None:
            raise ValueError("refused or errored preflight requires a category")
        return self
