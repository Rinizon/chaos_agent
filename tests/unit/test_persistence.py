from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from chaos_agent.adapters.persistence.database import create_database_engine
from chaos_agent.adapters.persistence.models import Base
from chaos_agent.adapters.persistence.repositories import ExperimentConflict, ExperimentRepository
from chaos_agent.domain.experiment import ExperimentRequest, ExperimentState, calculate_expiry


def repository(tmp_path) -> tuple[Session, ExperimentRepository]:
    engine = create_database_engine(tmp_path / "chaos-agent.db")
    Base.metadata.create_all(engine)
    session = Session(engine)
    return session, ExperimentRepository(session)


def request() -> ExperimentRequest:
    return ExperimentRequest(
        target_id=uuid4(),
        target_label="dev",
        scenario_name="synthetic",
        scenario_version="1.0.0",
        initiator="test",
    )


def test_schedule_and_transition_are_persisted_atomically(tmp_path) -> None:
    session, repo = repository(tmp_path)
    item = request()
    now = datetime.now(UTC)
    identifier = repo.schedule(item, calculate_expiry(now, 10), actor="test")
    repo.transition(
        str(identifier),
        ExperimentState.PREFLIGHT,
        reason="started",
        actor="test",
        expected_revision=0,
    )
    session.commit()
    row = repo.get(str(identifier))
    assert row is not None and row.state == "preflight" and row.revision == 1


def test_one_active_experiment_per_target(tmp_path) -> None:
    session, repo = repository(tmp_path)
    item = request()
    repo.schedule(item, datetime.now(UTC) + timedelta(seconds=10), actor="test")
    with pytest.raises(ExperimentConflict):
        repo.schedule(item, datetime.now(UTC) + timedelta(seconds=10), actor="test")
    session.rollback()


def test_claim_cannot_overwrite_an_unexpired_owner(tmp_path) -> None:
    session, repo = repository(tmp_path)
    identifier = repo.schedule(request(), datetime.now(UTC) + timedelta(seconds=30), actor="test")
    session.commit()
    now = datetime.now(UTC)
    assert repo.claim_next("supervisor-one", now, 30) is not None
    session.commit()

    second_session = Session(session.bind)
    second_repo = ExperimentRepository(second_session)
    assert second_repo.claim_next("supervisor-two", now, 30) is None
    row = second_repo.get(str(identifier))
    assert row is not None and row.owner_instance_id == "supervisor-one"
