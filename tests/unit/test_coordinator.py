from datetime import UTC, datetime, timedelta
from uuid import uuid4

from pydantic import BaseModel
from sqlalchemy.orm import Session

from chaos_agent.adapters.persistence.database import create_database_engine
from chaos_agent.adapters.persistence.models import Base
from chaos_agent.application.coordinator import ExperimentCoordinator
from chaos_agent.domain.experiment import ExperimentRequest, ExperimentState, SanitizedEvidence
from chaos_agent.domain.scenario import CleanupContext, ScenarioContext


class Params(BaseModel):
    pass


class FakeScenario:
    name = "synthetic"
    version = "1.0.0"
    parameters_model = Params
    calls: list[str]

    def __init__(self, cleanup_ok: bool = True) -> None:
        self.calls = []
        self.cleanup_ok = cleanup_ok

    def inject(self, context: ScenarioContext, parameters: Params):
        self.calls.append("inject")
        return CleanupContext(
            version=self.version, values={"owned": context.experiment_id}
        ), SanitizedEvidence(status="ok", message="injected")

    def cleanup(self, context: ScenarioContext, cleanup_context: CleanupContext):
        self.calls.append("cleanup")
        return SanitizedEvidence(status="ok" if self.cleanup_ok else "failed", message="cleanup")

    def verify_cleanup(self, context: ScenarioContext, cleanup_context: CleanupContext):
        self.calls.append("verify_cleanup")
        return SanitizedEvidence(status="ok", message="verified")


class Preflight:
    def __init__(self, result: bool = True) -> None:
        self.result = result

    def check(self, experiment_id: str) -> bool:
        return self.result


class Clock:
    def __init__(self, current: datetime) -> None:
        self.current = current

    def now(self) -> datetime:
        return self.current


def setup(tmp_path, duration: int = 30):
    engine = create_database_engine(tmp_path / "agent.db")
    Base.metadata.create_all(engine)
    session = Session(engine)
    from chaos_agent.adapters.persistence.repositories import ExperimentRepository

    request = ExperimentRequest(
        target_id=uuid4(),
        target_label="dev",
        scenario_name="synthetic",
        scenario_version="1.0.0",
        requested_duration_seconds=duration,
        initiator="test",
    )
    identifier = ExperimentRepository(session).schedule(
        request, datetime.now(UTC) + timedelta(seconds=duration), actor="test"
    )
    session.commit()
    return session, str(identifier)


def test_successful_expiry_cleans_and_verifies(tmp_path) -> None:
    session, identifier = setup(tmp_path, 1)
    scenario = FakeScenario()
    result = ExperimentCoordinator(
        session, scenario, Preflight(), Clock(datetime.now(UTC) + timedelta(seconds=2))
    ).run_once(identifier)
    assert result is ExperimentState.PASSED
    assert scenario.calls == ["inject", "cleanup", "verify_cleanup"]


def test_preflight_refusal_never_injects(tmp_path) -> None:
    session, identifier = setup(tmp_path)
    scenario = FakeScenario()
    result = ExperimentCoordinator(session, scenario, Preflight(False)).run_once(identifier)
    assert result is ExperimentState.FAILED
    assert scenario.calls == []


def test_cleanup_failure_is_not_false_success(tmp_path) -> None:
    session, identifier = setup(tmp_path)
    scenario = FakeScenario(False)
    result = ExperimentCoordinator(
        session, scenario, Preflight(), Clock(datetime.now(UTC) + timedelta(seconds=2))
    ).run_once(identifier)
    assert result is ExperimentState.CLEANUP_FAILED
