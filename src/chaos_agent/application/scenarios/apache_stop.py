"""Bounded Apache-stop scenario contract."""

from typing import Protocol

from pydantic import BaseModel, ConfigDict, StrictInt, model_validator

from chaos_agent.domain.experiment import SanitizedEvidence
from chaos_agent.domain.scenario import CleanupContext, ScenarioContext
from chaos_agent.domain.target import ApacheControlResponse


class ApacheStopParameters(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    duration_seconds: StrictInt = 300

    @model_validator(mode="after")
    def bounded(self) -> "ApacheStopParameters":
        if not 1 <= self.duration_seconds <= 3600:
            raise ValueError("duration_seconds must be between 1 and 3600")
        return self


class ApacheControlPort(Protocol):
    def apache_stop_preflight(self, context: ScenarioContext) -> ApacheControlResponse: ...
    def apache_stop(self, context: ScenarioContext) -> ApacheControlResponse: ...
    def apache_start(self, context: ScenarioContext) -> ApacheControlResponse: ...


class ApacheStopScenario:
    name = "apache-stop"
    version = "1.0.0"
    description = "Stop the configured Apache service for a bounded interval and verify recovery."
    parameters_model = ApacheStopParameters
    required_capabilities = ("apache_service_control", "apache_status", "website_observation")
    max_duration_seconds = 3600

    def __init__(self, control: ApacheControlPort) -> None:
        self.control = control

    def preflight(
        self, context: ScenarioContext, parameters: ApacheStopParameters
    ) -> SanitizedEvidence:
        response = self.control.apache_stop_preflight(context)
        if not response.installed:
            return SanitizedEvidence(status="failed", message="Apache is not installed")
        if not response.active:
            return SanitizedEvidence(status="failed", message="Apache baseline is inactive")
        return SanitizedEvidence(status="ok", message="Apache baseline is active")

    def inject(
        self, context: ScenarioContext, parameters: ApacheStopParameters
    ) -> tuple[CleanupContext, SanitizedEvidence]:
        response = self.control.apache_stop(context)
        if response.active or not response.changed:
            raise RuntimeError("Apache stop was not verified")
        return (
            CleanupContext(version=self.version, values={"apache_stop_confirmed": "true"}),
            SanitizedEvidence(status="ok", message="Apache stop verified"),
        )

    def verify_active(
        self, context: ScenarioContext, parameters: ApacheStopParameters
    ) -> SanitizedEvidence:
        response = self.control.apache_stop_preflight(context)
        return SanitizedEvidence(
            status="ok" if not response.active else "failed",
            message="Apache is inactive" if not response.active else "Apache remains active",
        )

    def cleanup(
        self, context: ScenarioContext, cleanup_context: CleanupContext
    ) -> SanitizedEvidence:
        if cleanup_context.values.get("apache_stop_confirmed") != "true":
            return SanitizedEvidence(status="failed", message="Apache stop ownership is unproven")
        response = self.control.apache_start(context)
        return SanitizedEvidence(
            status="ok" if response.active else "failed",
            message="Apache cleanup completed"
            if response.active
            else "Apache cleanup was not verified",
        )

    def verify_cleanup(
        self, context: ScenarioContext, cleanup_context: CleanupContext
    ) -> SanitizedEvidence:
        response = self.control.apache_stop_preflight(context)
        return SanitizedEvidence(
            status="ok" if response.active else "failed",
            message="Apache is active after cleanup"
            if response.active
            else "Apache remains inactive",
        )
