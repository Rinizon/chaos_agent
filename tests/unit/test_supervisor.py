from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy.orm import Session

from chaos_agent.adapters.persistence.database import create_database_engine
from chaos_agent.adapters.persistence.models import Base
from chaos_agent.adapters.persistence.repositories import ExperimentRepository
from chaos_agent.application.supervisor import Supervisor
from chaos_agent.domain.experiment import ExperimentRequest, ExperimentState


def test_restart_reconciles_injecting_without_reinjection(tmp_path, monkeypatch) -> None:
    engine = create_database_engine(tmp_path / "agent.db")
    Base.metadata.create_all(engine)
    session = Session(engine)
    request = ExperimentRequest(
        target_id=uuid4(),
        target_label="dev",
        scenario_name="synthetic",
        scenario_version="1.0.0",
        initiator="test",
    )
    identifier = ExperimentRepository(session).schedule(
        request, datetime.now(UTC) + timedelta(seconds=30), actor="test"
    )
    session.commit()
    repo = ExperimentRepository(session)
    repo.transition(
        str(identifier), ExperimentState.PREFLIGHT, reason="test", actor="test", expected_revision=0
    )
    repo.transition(
        str(identifier), ExperimentState.INJECTING, reason="test", actor="test", expected_revision=1
    )
    session.commit()

    class FakeCoordinator:
        def run_once(self, experiment_id):
            return ExperimentState.CLEANUP_FAILED

    class Factory:
        def __call__(self, session, name):
            return FakeCoordinator()

    assert Supervisor(session, Factory()).reconcile() == [ExperimentState.CLEANUP_FAILED]
    assert repo.get(str(identifier)).state == "cleaning_up"
