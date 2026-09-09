"""Production supervisor dependency wiring for the reviewed scenario catalog."""

import asyncio
from collections.abc import Callable
from typing import Any, cast

from sqlalchemy.orm import Session

from chaos_agent.adapters.http_observer import HttpxSiteObserver
from chaos_agent.adapters.openssh import OpenSshTransport
from chaos_agent.application.coordinator import ExperimentCoordinator
from chaos_agent.application.preflight import PreflightService
from chaos_agent.config import Settings
from chaos_agent.domain.scenario import CleanupContext, ScenarioContext
from chaos_agent.domain.target import RemoteOperation

from .scenarios.apache_stop import ApacheStopScenario
from .scenarios.cpu_pressure import CpuPressureScenario
from .scenarios.disk_pressure import DiskPressureScenario


class SshScenarioControl:
    def __init__(self, settings: Settings) -> None:
        self.config = settings.require_target_access()
        self.transport = OpenSshTransport()

    def call(self, operation: RemoteOperation) -> Any:
        return asyncio.run(self.transport.execute(self.config, operation))

    def apache_stop_preflight(self, context: ScenarioContext) -> Any:
        return self.call(RemoteOperation.APACHE_STOP_PREFLIGHT)
    def apache_stop(self, context: ScenarioContext) -> Any:
        return self.call(RemoteOperation.APACHE_STOP)
    def apache_start(self, context: ScenarioContext) -> Any:
        return self.call(RemoteOperation.APACHE_START)
    def cpu_pressure_preflight(self, context: ScenarioContext, parameters: Any) -> Any:
        return self.call(RemoteOperation.CPU_PRESSURE_PREFLIGHT)
    def preflight(self, context: ScenarioContext, parameters: Any) -> Any:
        return self.cpu_pressure_preflight(context, parameters)
    def start(self, context: ScenarioContext, parameters: Any) -> Any:
        return self.cpu_pressure_start(context, parameters)
    def stop(self, context: ScenarioContext, cleanup: CleanupContext) -> Any:
        return self.cpu_pressure_stop(context, cleanup)
    def cpu_pressure_start(self, context: ScenarioContext, parameters: Any) -> Any:
        return self.call(RemoteOperation.CPU_PRESSURE_START)
    def cpu_pressure_stop(self, context: ScenarioContext, cleanup: CleanupContext) -> Any:
        return self.call(RemoteOperation.CPU_PRESSURE_STOP)
    def disk_pressure_preflight(self, context: ScenarioContext, parameters: Any) -> Any:
        return self.call(RemoteOperation.DISK_PRESSURE_PREFLIGHT)
    def disk_pressure_start(self, context: ScenarioContext, parameters: Any) -> Any:
        return self.call(RemoteOperation.DISK_PRESSURE_START)
    def disk_pressure_stop(self, context: ScenarioContext, cleanup: CleanupContext) -> Any:
        return self.call(RemoteOperation.DISK_PRESSURE_STOP)
    def disk_preflight(self, context: ScenarioContext, parameters: Any) -> Any:
        return self.disk_pressure_preflight(context, parameters)
    def disk_start(self, context: ScenarioContext, parameters: Any) -> Any:
        return self.disk_pressure_start(context, parameters)
    def disk_stop(self, context: ScenarioContext, cleanup: CleanupContext) -> Any:
        return self.disk_pressure_stop(context, cleanup)


class ProductionPreflight:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.config = settings.require_target_access()

    def check(self, experiment_id: str) -> bool:
        report = asyncio.run(
            PreflightService(OpenSshTransport(), HttpxSiteObserver()).run(self.config)
        )
        return report.outcome.value == "pass"


def coordinator_factory(settings: Settings) -> Callable[[Session, str], ExperimentCoordinator]:
    control = SshScenarioControl(settings)
    scenarios = {
        "apache-stop": ApacheStopScenario(control),
        "cpu-pressure": CpuPressureScenario(control),
        "disk-pressure": DiskPressureScenario(control),
    }
    def factory(session: Session, name: str) -> ExperimentCoordinator:
        scenario = scenarios.get(name)
        if scenario is None:
            raise KeyError("scenario unavailable")
        return ExperimentCoordinator(
            session, cast(Any, scenario), ProductionPreflight(settings)
        )
    return factory
