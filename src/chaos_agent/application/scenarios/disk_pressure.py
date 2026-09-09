"""Bounded disk pressure restricted to dedicated test storage."""

from typing import Protocol

from pydantic import BaseModel, ConfigDict, StrictInt, model_validator

from chaos_agent.domain.experiment import SanitizedEvidence
from chaos_agent.domain.scenario import CleanupContext, ScenarioContext
from chaos_agent.domain.target import DiskPressureResponse


class DiskPressureParameters(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    duration_seconds: StrictInt = 300
    allocation_mib: StrictInt = 256
    chunk_mib: StrictInt = 16

    @model_validator(mode="after")
    def bounded(self) -> "DiskPressureParameters":
        if not 1 <= self.duration_seconds <= 900:
            raise ValueError("duration_seconds must be between 1 and 900")
        if not 1 <= self.allocation_mib <= 4096:
            raise ValueError("allocation_mib must be between 1 and 4096")
        if not 1 <= self.chunk_mib <= 64 or self.chunk_mib > self.allocation_mib:
            raise ValueError("chunk_mib must be between 1 and allocation_mib")
        return self


class DiskPressureControl(Protocol):
    def preflight(
        self, context: ScenarioContext, parameters: DiskPressureParameters
    ) -> DiskPressureResponse: ...
    def start(
        self, context: ScenarioContext, parameters: DiskPressureParameters
    ) -> DiskPressureResponse: ...
    def stop(self, context: ScenarioContext, cleanup: CleanupContext) -> DiskPressureResponse: ...


class DiskPressureScenario:
    name = "disk-pressure"
    version = "1.0.0"
    description = "Create bounded disk pressure on dedicated test storage."
    parameters_model = DiskPressureParameters
    required_capabilities = ("dedicated_test_storage", "capacity_status", "website_observation")
    max_duration_seconds = 900

    def __init__(self, control: DiskPressureControl) -> None:
        self.control = control

    def preflight(
        self, context: ScenarioContext, parameters: DiskPressureParameters
    ) -> SanitizedEvidence:
        result = self.control.preflight(context, parameters)
        needed = parameters.allocation_mib * 1024 * 1024
        if (
            not result.storage_owned
            or result.artifact_owned
            or result.free_bytes - needed < result.reserve_bytes
        ):
            return SanitizedEvidence(
                status="failed", message="Dedicated storage reserve is unavailable"
            )
        return SanitizedEvidence(status="ok", message="Dedicated storage reserve is available")

    def inject(
        self, context: ScenarioContext, parameters: DiskPressureParameters
    ) -> tuple[CleanupContext, SanitizedEvidence]:
        result = self.control.start(context, parameters)
        if not result.artifact_owned or not result.active:
            raise RuntimeError("disk artifact ownership was not verified")
        return CleanupContext(
            version=self.version, values={"artifact_owned": "true"}
        ), SanitizedEvidence(status="ok", message="Disk artifact allocated in dedicated storage")

    def verify_active(
        self, context: ScenarioContext, parameters: DiskPressureParameters
    ) -> SanitizedEvidence:
        result = self.control.preflight(context, parameters)
        return SanitizedEvidence(
            status="ok" if result.artifact_owned else "failed",
            message="Disk artifact is active"
            if result.artifact_owned
            else "Disk artifact is absent",
        )

    def cleanup(
        self, context: ScenarioContext, cleanup_context: CleanupContext
    ) -> SanitizedEvidence:
        if cleanup_context.values.get("artifact_owned") != "true":
            return SanitizedEvidence(status="failed", message="Disk artifact ownership is unproven")
        result = self.control.stop(context, cleanup_context)
        return SanitizedEvidence(
            status="ok" if not result.artifact_owned else "failed",
            message="Disk artifact removed"
            if not result.artifact_owned
            else "Disk artifact remains",
        )

    def verify_cleanup(
        self, context: ScenarioContext, cleanup_context: CleanupContext
    ) -> SanitizedEvidence:
        return self.cleanup(context, cleanup_context)
