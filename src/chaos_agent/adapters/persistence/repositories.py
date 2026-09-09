"""Transactional experiment repository."""

from datetime import UTC, datetime, timedelta
from typing import Any, cast

from sqlalchemy import CursorResult, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from chaos_agent.domain.experiment import (
    ExperimentId,
    ExperimentRequest,
    ExperimentState,
    validate_transition,
)
from chaos_agent.domain.preflight import SiteObservation

from .models import (
    ActionAttemptRow,
    ControlRequestRow,
    ExperimentRow,
    ExperimentTransitionRow,
    SiteObservationRow,
)


class ExperimentConflict(ValueError):
    """A duplicate target or stale revision prevented a safe write."""


class ExperimentRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def schedule(
        self, request: ExperimentRequest, expires_at: datetime, *, actor: str
    ) -> ExperimentId:
        experiment_id = ExperimentId.new()
        now = datetime.now(UTC)
        row = ExperimentRow(
            experiment_id=experiment_id,
            target_id=str(request.target_id),
            target_label=request.target_label,
            scenario_name=request.scenario_name,
            scenario_version=request.scenario_version,
            parameters=request.parameters,
            requested_duration_seconds=request.requested_duration_seconds,
            expires_at=expires_at,
            initiator=request.initiator,
            state=ExperimentState.PLANNED.value,
            revision=0,
            created_at=now,
            updated_at=now,
        )
        try:
            self.session.add(row)
            self.session.flush()
            self.session.add(
                ExperimentTransitionRow(
                    experiment_id=experiment_id,
                    sequence=1,
                    from_state=None,
                    to_state="planned",
                    occurred_at=now,
                    reason="scheduled",
                    actor=actor,
                    revision=0,
                    summary="scheduled",
                )
            )
            self.session.flush()
        except IntegrityError as error:
            self.session.rollback()
            raise ExperimentConflict("target already has an active experiment") from error
        return experiment_id

    def transition(
        self,
        experiment_id: str,
        target: ExperimentState,
        *,
        reason: str,
        actor: str,
        expected_revision: int,
    ) -> None:
        row = self.session.get(ExperimentRow, ExperimentId.validate(experiment_id))
        if row is None:
            raise KeyError("experiment not found")
        current = ExperimentState(row.state)
        validate_transition(current, target)
        result = cast(CursorResult[Any], self.session.execute(
            update(ExperimentRow)
            .where(
                ExperimentRow.experiment_id == experiment_id,
                ExperimentRow.revision == expected_revision,
            )
            .values(
                state=target.value, revision=expected_revision + 1, updated_at=datetime.now(UTC)
            )
        ))
        if result.rowcount != 1:
            raise ExperimentConflict("experiment revision is stale")
        self.session.add(
            ExperimentTransitionRow(
                experiment_id=experiment_id,
                sequence=expected_revision + 2,
                from_state=current.value,
                to_state=target.value,
                occurred_at=datetime.now(UTC),
                reason=reason,
                actor=actor,
                revision=expected_revision + 1,
                summary=reason,
            )
        )

    def get(self, experiment_id: str) -> ExperimentRow | None:
        return self.session.get(ExperimentRow, ExperimentId.validate(experiment_id))

    def claim_next(
        self, instance_id: str, now: datetime, lease_seconds: int
    ) -> ExperimentRow | None:
        """Claim the oldest planned or expired-lease experiment with CAS semantics."""
        candidate = self.session.scalars(
            select(ExperimentRow)
            .where(
                ExperimentRow.state.in_(["planned", "preflight", "cleaning_up", "cleanup_failed"]),
                (
                    ExperimentRow.owner_instance_id.is_(None)
                    | (ExperimentRow.lease_expires_at < now)
                ),
            )
            .order_by(ExperimentRow.created_at, ExperimentRow.experiment_id)
            .limit(1)
        ).first()
        if candidate is None:
            return None
        result = cast(CursorResult[Any], self.session.execute(
            update(ExperimentRow)
            .where(
                ExperimentRow.experiment_id == candidate.experiment_id,
                ExperimentRow.revision == candidate.revision,
            )
            .values(
                owner_instance_id=instance_id,
                lease_acquired_at=now,
                lease_expires_at=now + timedelta(seconds=lease_seconds),
            )
        ))
        if result.rowcount != 1:
            self.session.rollback()
            return None
        self.session.flush()
        return self.get(candidate.experiment_id)

    def renew_lease(
        self, experiment_id: str, instance_id: str, now: datetime, lease_seconds: int
    ) -> bool:
        result = cast(CursorResult[Any], self.session.execute(
            update(ExperimentRow)
            .where(
                ExperimentRow.experiment_id == experiment_id,
                ExperimentRow.owner_instance_id == instance_id,
            )
            .values(lease_expires_at=now + timedelta(seconds=lease_seconds))
        ))
        return result.rowcount == 1

    def release_lease(self, experiment_id: str, instance_id: str) -> bool:
        result = cast(CursorResult[Any], self.session.execute(
            update(ExperimentRow)
            .where(
                ExperimentRow.experiment_id == experiment_id,
                ExperimentRow.owner_instance_id == instance_id,
            )
            .values(owner_instance_id=None, lease_acquired_at=None, lease_expires_at=None)
        ))
        return result.rowcount == 1

    def record_attempt(
        self,
        experiment_id: str,
        action_kind: str,
        attempt: int,
        result_category: str,
        evidence: dict[str, object],
        *,
        started_at: datetime,
        completed_at: datetime | None = None,
    ) -> bool:
        """Append one bounded action audit record, idempotently."""
        row = ActionAttemptRow(
            experiment_id=experiment_id,
            action_kind=action_kind[:32],
            attempt=attempt,
            idempotency_key=f"{experiment_id}:{action_kind}:{attempt}",
            started_at=started_at,
            completed_at=completed_at,
            result_category=result_category[:32],
            evidence=evidence,
        )
        try:
            self.session.add(row)
            self.session.flush()
        except IntegrityError:
            self.session.rollback()
            return False
        return True

    def pending_control_requests(self, experiment_id: str | None = None) -> list[ControlRequestRow]:
        query = select(ControlRequestRow).where(ControlRequestRow.processing_state == "pending")
        if experiment_id is not None:
            query = query.where(ControlRequestRow.experiment_id == experiment_id)
        return list(self.session.scalars(query.order_by(ControlRequestRow.requested_at)))

    def complete_control_request(self, request_id: int, state: str = "processed") -> None:
        self.session.execute(
            update(ControlRequestRow)
            .where(ControlRequestRow.id == request_id)
            .values(processing_state=state)
        )

    def list_active(self) -> list[ExperimentRow]:
        return list(
            self.session.scalars(
                select(ExperimentRow)
                .where(
                    ~ExperimentRow.state.in_(
                        ["passed", "cancelled", "failed", "operator_attention"]
                    )
                )
                .order_by(ExperimentRow.created_at, ExperimentRow.experiment_id)
            )
        )

    def list_history(
        self, *, scenario: str | None = None, state: str | None = None, limit: int = 100
    ) -> list[ExperimentRow]:
        """Return bounded, deterministic experiment history."""
        limit = max(1, min(limit, 100))
        query = select(ExperimentRow)
        if scenario is not None:
            query = query.where(ExperimentRow.scenario_name == scenario)
        if state is not None:
            query = query.where(ExperimentRow.state == state)
        return list(
            self.session.scalars(
                query.order_by(
                    ExperimentRow.created_at.desc(), ExperimentRow.experiment_id.desc()
                ).limit(limit)
            )
        )

    def request_control(
        self, experiment_id: str, kind: str, requester: str, idempotency_key: str
    ) -> bool:
        """Durably enqueue an idempotent cancellation or reconciliation request."""
        from sqlalchemy.exc import IntegrityError

        ExperimentId.validate(experiment_id)
        if self.get(experiment_id) is None:
            raise KeyError("experiment not found")
        request = ControlRequestRow(
            experiment_id=experiment_id,
            request_kind=kind,
            requester=requester,
            requested_at=datetime.now(UTC),
            processing_state="pending",
            idempotency_key=idempotency_key,
        )
        try:
            self.session.add(request)
            self.session.flush()
        except IntegrityError:
            self.session.rollback()
            return False
        return True

    def record_observation(
        self,
        experiment_id: str,
        phase: str,
        sequence: int,
        observation: SiteObservation,
    ) -> None:
        self.session.add(
            SiteObservationRow(
                experiment_id=ExperimentId.validate(experiment_id),
                phase=phase,
                sequence=sequence,
                observed_at=datetime.now(UTC),
                available=200 <= observation.status_code < 400,
                status_code=observation.status_code,
                duration_ms=observation.duration_ms,
                content_matched=observation.content_matched,
            )
        )
