from datetime import UTC, datetime

import pytest

from chaos_agent.domain.integration import IntegrationEvent


def test_integration_event_is_versioned_and_bounded() -> None:
    event = IntegrationEvent.create(
        event_type="experiment.finalized",
        experiment_id="exp_" + "a" * 32,
        scenario_name="apache-stop",
        scenario_version="1.0.0",
        target_ref="development-web",
        correlation_id="corr-1",
        actor="supervisor",
        payload={"outcome": "failed"},
    )
    assert event.schema_version == 1
    assert event.payload == {"outcome": "failed"}
    assert event.occurred_at.tzinfo is UTC


def test_integration_event_rejects_unknown_fields() -> None:
    with pytest.raises(ValueError):
        IntegrationEvent(
            event_type="experiment.finalized", experiment_id="exp_" + "a" * 32,
            scenario_name="apache-stop", scenario_version="1.0.0", target_ref="x",
            occurred_at=datetime.now(UTC), correlation_id="c", actor="a", secret="nope"
        )
