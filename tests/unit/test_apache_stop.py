import pytest
from pydantic import ValidationError

from chaos_agent.application.scenarios.apache_stop import ApacheStopParameters, ApacheStopScenario
from chaos_agent.domain.scenario import ScenarioContext
from chaos_agent.domain.target import ApacheControlResponse


def response(operation: str, *, active: bool, changed: bool) -> ApacheControlResponse:
    return ApacheControlResponse(
        protocol_version=1,
        helper_version="0.1.0",
        operation=operation,
        marker_schema_version=1,
        target_id="8d047f58-0dc7-4d61-a165-82b02edbc2c8",
        environment="development",
        role="web",
        apache_service="apache2.service",
        effective_uid=0,
        installed=True,
        active=active,
        changed=changed,
    )


class FakeControl:
    def __init__(self) -> None:
        self.active = True

    def apache_stop_preflight(self, context):
        return response("apache-stop-preflight", active=self.active, changed=False)

    def apache_stop(self, context):
        self.active = False
        return response("apache-stop", active=False, changed=True)

    def apache_start(self, context):
        self.active = True
        return response("apache-start", active=True, changed=True)


def test_apache_stop_has_bounded_successful_cleanup() -> None:
    scenario = ApacheStopScenario(FakeControl())
    context = ScenarioContext(experiment_id="exp_" + "a" * 32, target_id="target")
    params = ApacheStopParameters()

    assert scenario.preflight(context, params).status == "ok"
    cleanup, injected = scenario.inject(context, params)
    assert injected.status == "ok"
    assert scenario.verify_active(context, params).status == "ok"
    assert scenario.cleanup(context, cleanup).status == "ok"
    assert scenario.verify_cleanup(context, cleanup).status == "ok"


def test_apache_stop_refuses_unbounded_duration() -> None:
    with pytest.raises(ValidationError):
        ApacheStopParameters(duration_seconds=3601)
