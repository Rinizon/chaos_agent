"""Typed scenario boundary; implementations are supplied in later phases."""

from typing import Protocol, TypeVar

from pydantic import BaseModel, ConfigDict, Field, StrictStr

from chaos_agent.domain.experiment import SanitizedEvidence


class ScenarioContext(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    experiment_id: StrictStr = Field(pattern=r"^exp_[0-9a-f]{32}$")
    target_id: StrictStr


class CleanupContext(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    version: StrictStr = Field(pattern=r"^[0-9]+\.[0-9]+\.[0-9]+$")
    values: dict[str, StrictStr] = Field(default_factory=dict)


ParametersT = TypeVar("ParametersT", bound=BaseModel)


class Scenario(Protocol[ParametersT]):
    name: str
    version: str
    description: str
    parameters_model: type[ParametersT]
    required_capabilities: tuple[str, ...]
    max_duration_seconds: int

    def preflight(self, context: ScenarioContext, parameters: ParametersT) -> SanitizedEvidence: ...
    def inject(
        self, context: ScenarioContext, parameters: ParametersT
    ) -> tuple[CleanupContext, SanitizedEvidence]: ...
    def verify_active(
        self, context: ScenarioContext, parameters: ParametersT
    ) -> SanitizedEvidence: ...
    def cleanup(
        self, context: ScenarioContext, cleanup_context: CleanupContext
    ) -> SanitizedEvidence: ...
    def verify_cleanup(
        self, context: ScenarioContext, cleanup_context: CleanupContext
    ) -> SanitizedEvidence: ...
