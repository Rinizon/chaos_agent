"""Deterministic experiment coordinator with cleanup-first safety behavior."""

from datetime import UTC, datetime
from typing import Protocol

from sqlalchemy.orm import Session

from chaos_agent.adapters.persistence.repositories import ExperimentRepository
from chaos_agent.domain.experiment import ExperimentState
from chaos_agent.domain.scenario import CleanupContext, Scenario, ScenarioContext


class PreflightPort(Protocol):
    def check(self, experiment_id: str) -> bool: ...


class ClockPort(Protocol):
    def now(self) -> datetime: ...


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(UTC)


class ExperimentCoordinator:
    """Run one claimed experiment; every uncertain mutation goes to cleanup."""

    def __init__(
        self,
        session: Session,
        scenario: Scenario,
        preflight: PreflightPort,
        clock: ClockPort | None = None,
        actor: str = "supervisor",
    ) -> None:
        self.session = session
        self.repository = ExperimentRepository(session)
        self.scenario = scenario
        self.preflight = preflight
        self.clock = clock or SystemClock()
        self.actor = actor

    def run_once(self, experiment_id: str) -> ExperimentState:
        row = self.repository.get(experiment_id)
        if row is None:
            raise KeyError("experiment not found")
        state = ExperimentState(row.state)
        if state in {ExperimentState.PLANNED, ExperimentState.PREFLIGHT}:
            state = self._prepare(row)
        if state is ExperimentState.INJECTING:
            state = self._inject(row)
        row = self.repository.get(experiment_id)
        if row is None:
            raise KeyError("experiment not found")
        state = ExperimentState(row.state)
        if state is ExperimentState.ACTIVE and self.clock.now() >= row.expires_at.replace(
            tzinfo=UTC
        ):
            self.repository.transition(
                experiment_id,
                ExperimentState.EXPIRED,
                reason="expired",
                actor=self.actor,
                expected_revision=row.revision,
            )
            self.session.commit()
            row = self.repository.get(experiment_id)
            state = ExperimentState(row.state) if row else state
        if state in {
            ExperimentState.INJECTING,
            ExperimentState.ACTIVE,
            ExperimentState.EXPIRED,
            ExperimentState.CANCELLATION_REQUESTED,
            ExperimentState.CLEANING_UP,
            ExperimentState.CLEANUP_FAILED,
        }:
            if state in {
                ExperimentState.INJECTING,
                ExperimentState.ACTIVE,
                ExperimentState.EXPIRED,
                ExperimentState.CANCELLATION_REQUESTED,
            }:
                current = self.repository.get(experiment_id)
                self.repository.transition(
                    experiment_id,
                    ExperimentState.CLEANING_UP,
                    reason="cleanup_required",
                    actor=self.actor,
                    expected_revision=current.revision,
                )
                self.session.commit()
            state = self._cleanup(experiment_id)
        return state

    def _prepare(self, row) -> ExperimentState:
        if ExperimentState(row.state) is ExperimentState.PLANNED:
            self.repository.transition(
                row.experiment_id,
                ExperimentState.PREFLIGHT,
                reason="preflight_started",
                actor=self.actor,
                expected_revision=row.revision,
            )
        if not self.preflight.check(row.experiment_id):
            current = self.repository.get(row.experiment_id)
            self.repository.transition(
                row.experiment_id,
                ExperimentState.FAILED,
                reason="preflight_refused",
                actor=self.actor,
                expected_revision=current.revision,
            )
            self.session.commit()
            return ExperimentState.FAILED
        current = self.repository.get(row.experiment_id)
        self.repository.transition(
            row.experiment_id,
            ExperimentState.INJECTING,
            reason="preflight_passed",
            actor=self.actor,
            expected_revision=current.revision,
        )
        self.session.commit()
        return ExperimentState.INJECTING

    def _inject(self, row) -> ExperimentState:
        context = ScenarioContext(experiment_id=row.experiment_id, target_id=row.target_id)
        try:
            cleanup, evidence = self.scenario.inject(
                context, self.scenario.parameters_model.model_validate(row.parameters)
            )
            if evidence.status != "ok":
                raise RuntimeError("injection was not verified")
            current = self.repository.get(row.experiment_id)
            self.repository.transition(
                row.experiment_id,
                ExperimentState.ACTIVE,
                reason="injection_verified",
                actor=self.actor,
                expected_revision=current.revision,
            )
            current.cleanup_context = cleanup.model_dump()
            self.session.commit()
            return ExperimentState.ACTIVE
        except Exception:
            current = self.repository.get(row.experiment_id)
            if current and ExperimentState(current.state) is ExperimentState.INJECTING:
                self.repository.transition(
                    row.experiment_id,
                    ExperimentState.CLEANING_UP,
                    reason="injection_uncertain",
                    actor=self.actor,
                    expected_revision=current.revision,
                )
                self.session.commit()
            return ExperimentState.CLEANING_UP

    def _cleanup(self, experiment_id: str) -> ExperimentState:
        row = self.repository.get(experiment_id)
        if row is None:
            raise KeyError("experiment not found")
        context = ScenarioContext(experiment_id=row.experiment_id, target_id=row.target_id)
        cleanup_context = CleanupContext.model_validate(
            row.cleanup_context or {"version": self.scenario.version}
        )
        evidence = self.scenario.cleanup(context, cleanup_context)
        if evidence.status != "ok":
            self.repository.transition(
                experiment_id,
                ExperimentState.CLEANUP_FAILED,
                reason="cleanup_failed",
                actor=self.actor,
                expected_revision=row.revision,
            )
            self.session.commit()
            return ExperimentState.CLEANUP_FAILED
        self.repository.transition(
            experiment_id,
            ExperimentState.VERIFYING,
            reason="cleanup_succeeded",
            actor=self.actor,
            expected_revision=row.revision,
        )
        row = self.repository.get(experiment_id)
        verified = self.scenario.verify_cleanup(context, cleanup_context).status == "ok"
        target = ExperimentState.PASSED if verified else ExperimentState.OPERATOR_ATTENTION
        self.repository.transition(
            experiment_id,
            target,
            reason="verification_passed" if verified else "verification_failed",
            actor=self.actor,
            expected_revision=row.revision,
        )
        self.session.commit()
        return target
