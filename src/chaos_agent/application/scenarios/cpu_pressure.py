"""Bounded, experiment-owned CPU pressure scenario."""

from typing import Protocol

from pydantic import BaseModel, ConfigDict, StrictInt, model_validator

from chaos_agent.domain.experiment import SanitizedEvidence
from chaos_agent.domain.scenario import CleanupContext, ScenarioContext
from chaos_agent.domain.target import CpuPressureResponse


class CpuPressureParameters(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    duration_seconds: StrictInt = 300
    worker_count: StrictInt = 1
    target_cpu_percent: StrictInt = 50

    @model_validator(mode="after")
    def bounded(self) -> "CpuPressureParameters":
        if not 1 <= self.duration_seconds <= 900:
            raise ValueError("duration_seconds must be between 1 and 900")
        if not 1 <= self.worker_count <= 8:
            raise ValueError("worker_count must be between 1 and 8")
        if not 10 <= self.target_cpu_percent <= 80:
            raise ValueError("target_cpu_percent must be between 10 and 80")
        return self


class CpuPressureControl(Protocol):
    def preflight(
        self, context: ScenarioContext, parameters: CpuPressureParameters
    ) -> CpuPressureResponse: ...
    def start(
        self, context: ScenarioContext, parameters: CpuPressureParameters
    ) -> CpuPressureResponse: ...
    def stop(self, context: ScenarioContext, cleanup: CleanupContext) -> CpuPressureResponse: ...


class CpuPressureScenario:
    name = "cpu-pressure"
    version = "1.0.0"
    description = "Create bounded CPU pressure while preserving management and cleanup capacity."
    parameters_model = CpuPressureParameters
    required_capabilities = ("cpu_pressure", "cpu_status", "website_observation")
    max_duration_seconds = 900

    def __init__(self, control: CpuPressureControl) -> None:
        self.control = control

    def preflight(
        self, context: ScenarioContext, parameters: CpuPressureParameters
    ) -> SanitizedEvidence:
        result = self.control.preflight(context, parameters)
        if result.active or not result.workload_owned:
            return SanitizedEvidence(
                status="failed", message="CPU workload scope is already active"
            )
        if result.logical_cpu_count < 2:
            return SanitizedEvidence(
                status="failed", message="CPU reserve requires at least two CPUs"
            )
        return SanitizedEvidence(
            status="ok", message="CPU reserve and workload scope are available"
        )

    def inject(
        self, context: ScenarioContext, parameters: CpuPressureParameters
    ) -> tuple[CleanupContext, SanitizedEvidence]:
        result = self.control.start(context, parameters)
        if not result.active or not result.workload_owned:
            raise RuntimeError("CPU workload ownership was not verified")
        return CleanupContext(
            version=self.version, values={"workload_owned": "true"}
        ), SanitizedEvidence(status="ok", message="CPU workload started in owned scope")

    def verify_active(
        self, context: ScenarioContext, parameters: CpuPressureParameters
    ) -> SanitizedEvidence:
        result = self.control.preflight(context, parameters)
        return SanitizedEvidence(
            status="ok" if result.active and result.workload_owned else "failed",
            message="CPU workload is active" if result.active else "CPU workload is inactive",
        )

    def cleanup(
        self, context: ScenarioContext, cleanup_context: CleanupContext
    ) -> SanitizedEvidence:
        if cleanup_context.values.get("workload_owned") != "true":
            return SanitizedEvidence(status="failed", message="CPU workload ownership is unproven")
        result = self.control.stop(context, cleanup_context)
        return SanitizedEvidence(
            status="ok" if not result.active else "failed",
            message="CPU workload stopped" if not result.active else "CPU workload remains active",
        )

    def verify_cleanup(
        self, context: ScenarioContext, cleanup_context: CleanupContext
    ) -> SanitizedEvidence:
        result = self.control.stop(context, cleanup_context)
        return SanitizedEvidence(
            status="ok" if not result.active else "failed",
            message="CPU workload is absent"
            if not result.active
            else "CPU workload remains active",
        )
