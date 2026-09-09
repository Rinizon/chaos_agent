"""Durable append-only integration outbox."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from chaos_agent.domain.integration import IntegrationEvent

from .models import IntegrationEventRow


class IntegrationOutbox:
    def __init__(self, session: Session) -> None:
        self.session = session

    def append(self, event: IntegrationEvent) -> bool:
        if len(event.model_dump_json()) > 16_384:
            raise ValueError("integration event exceeds size limit")
        if self.session.get(IntegrationEventRow, str(event.event_id)) is not None:
            return False
        self.session.add(IntegrationEventRow(
            event_id=str(event.event_id), experiment_id=event.experiment_id,
            event_type=event.event_type, occurred_at=event.occurred_at,
            payload=event.model_dump(mode="json"), delivery_state="pending", attempts=0,
        ))
        self.session.flush()
        return True

    def pending(self, limit: int = 100) -> list[IntegrationEventRow]:
        return list(self.session.scalars(select(IntegrationEventRow)
            .where(IntegrationEventRow.delivery_state == "pending")
            .order_by(IntegrationEventRow.occurred_at).limit(max(1, min(limit, 100)))))
