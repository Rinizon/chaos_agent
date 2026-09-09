from fastapi.testclient import TestClient

from chaos_agent.api import create_app
from chaos_agent.config import Settings


def test_health_is_local_and_public() -> None:
    client = TestClient(create_app(Settings(api_bearer_token="x" * 16)))
    assert client.get("/health").json() == {"status": "ok", "service": "chaos-agent"}


def test_scenarios_require_bearer_token() -> None:
    client = TestClient(create_app(Settings(api_bearer_token="x" * 16)))
    assert client.get("/api/v1/scenarios").status_code == 401
    response = client.get("/api/v1/scenarios", headers={"Authorization": "Bearer " + "x" * 16})
    assert response.status_code == 200
    assert {item["name"] for item in response.json()["scenarios"]} == {
        "apache-stop", "cpu-pressure", "disk-pressure"
    }
