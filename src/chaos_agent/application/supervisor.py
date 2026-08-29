"""Background ownership and restart reconciliation for experiments."""

from collections.abc import Callable
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy.orm import Session

from chaos_agent.adapters.persistence.repositories import ExperimentRepository
from chaos_agent.application.coordinator import ExperimentCoordinator
from chaos_agent.domain.experiment import ExperimentState


class Supervisor:
    def __init__(
        self,
        session: Session,
        coordinator_factory: Callable[[Session, str], ExperimentCoordinator],
        actor: str = "supervisor",
        instance_id: str | None = None,
        lease_duration_seconds: int = 30,
    ) -> None:
        self.session = session
        self.coordinator_factory = coordinator_factory
        self.actor = actor
        self.instance_id = instance_id or f"sup_{uuid4().hex}"
        self.lease_duration_seconds = lease_duration_seconds

    def reconcile(self) -> list[ExperimentState]:
        """Reconcile all interrupted work without ever resuming injection blindly."""
        repository = ExperimentRepository(self.session)
        results: list[ExperimentState] = []
        for row in repository.list_active():
            state = ExperimentState(row.state)
            if state is ExperimentState.INJECTING:
                repository.transition(
                    row.experiment_id,
                    ExperimentState.CLEANING_UP,
                    reason="restart_uncertain_injection",
                    actor=self.actor,
                    expected_revision=row.revision,
                )
                self.session.commit()
            coordinator = self.coordinator_factory(self.session, row.scenario_name)
            results.append(coordinator.run_once(row.experiment_id))
        return results

    def run_once(self) -> list[ExperimentState]:
        repository = ExperimentRepository(self.session)
        results = self.reconcile()
        for request in repository.pending_control_requests():
            row = repository.get(request.experiment_id)
            if row is not None and request.request_kind == "cancel":
                state = ExperimentState(row.state)
                if state not in {ExperimentState.PASSED, ExperimentState.FAILED,
                                 ExperimentState.CANCELLED, ExperimentState.OPERATOR_ATTENTION}:
                    if state is ExperimentState.PLANNED:
                        repository.transition(row.experiment_id, ExperimentState.CANCELLED,
                                              reason="abort_requested", actor=request.requester,
                                              expected_revision=row.revision)
                    elif state is ExperimentState.ACTIVE:
                        repository.transition(
                            row.experiment_id,
                            ExperimentState.CANCELLATION_REQUESTED,
                                              reason="abort_requested", actor=request.requester,
                                              expected_revision=row.revision)
                    self.session.commit()
            repository.complete_control_request(request.id)
            self.session.commit()
        claimed = repository.claim_next(
            self.instance_id, datetime.now(UTC), self.lease_duration_seconds
        )
        if claimed is not None:
            self.session.commit()
            coordinator = self.coordinator_factory(self.session, claimed.scenario_name)
            results.append(coordinator.run_once(claimed.experiment_id))
            repository.release_lease(claimed.experiment_id, self.instance_id)
            self.session.commit()
        return results

    def run(self, stop: Callable[[], bool], poll_interval_seconds: float = 1.0) -> None:
        """Run supervision until the supplied shutdown predicate is true."""
        while not stop():
            self.run_once()
