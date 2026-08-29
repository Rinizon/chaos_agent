"""Background ownership and restart reconciliation for experiments."""

from collections.abc import Callable

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
    ) -> None:
        self.session = session
        self.coordinator_factory = coordinator_factory
        self.actor = actor

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
        return self.reconcile()
