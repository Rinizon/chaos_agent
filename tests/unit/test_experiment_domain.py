from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from pydantic import ValidationError

from chaos_agent.domain.experiment import (
    ExperimentId,
    ExperimentRequest,
    ExperimentState,
    calculate_expiry,
    validate_transition,
)
from chaos_agent.domain.scenario import CleanupContext, ScenarioContext


def test_experiment_ids_are_opaque_and_strict() -> None:
    identifier = ExperimentId.new()
    assert ExperimentId.validate(identifier) == identifier
    with pytest.raises(ValueError):
        ExperimentId.validate("exp_" + "A" * 32)


def test_request_defaults_and_bounds_duration() -> None:
    request = ExperimentRequest(
        target_id=uuid4(),
        target_label="dev",
        scenario_name="synthetic",
        scenario_version="1.0.0",
        initiator="test",
    )
    assert request.requested_duration_seconds == 300
    with pytest.raises(ValidationError):
        ExperimentRequest(
            target_id=uuid4(),
            target_label="dev",
            scenario_name="synthetic",
            scenario_version="1.0.0",
            initiator="test",
            requested_duration_seconds=3601,
        )


def test_every_transition_matches_spec_and_terminal_states_are_locked() -> None:
    allowed = [
        (ExperimentState.PLANNED, ExperimentState.PREFLIGHT),
        (ExperimentState.INJECTING, ExperimentState.CLEANING_UP),
        (ExperimentState.VERIFYING, ExperimentState.PASSED),
    ]
    for current, target in allowed:
        validate_transition(current, target)
    for current, target in [
        (ExperimentState.PLANNED, ExperimentState.ACTIVE),
        (ExperimentState.PASSED, ExperimentState.PLANNED),
        (ExperimentState.CLEANUP_FAILED, ExperimentState.PASSED),
    ]:
        with pytest.raises(ValueError):
            validate_transition(current, target)


def test_expiry_is_utc_and_duration_is_bounded() -> None:
    started = datetime(2026, 1, 1, tzinfo=UTC)
    assert calculate_expiry(started, 5) == started + timedelta(seconds=5)
    with pytest.raises(ValueError):
        calculate_expiry(datetime(2026, 1, 1), 5)


def test_context_models_reject_arbitrary_fields() -> None:
    assert (
        ScenarioContext(experiment_id="exp_" + "a" * 32, target_id="target").target_id == "target"
    )
    with pytest.raises(ValidationError):
        CleanupContext(version="1.0.0", values={"secret": "x"}, extra="nope")
