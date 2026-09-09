"""Authenticated HTTP adapter for the Chaos Agent application services."""

import secrets
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, ConfigDict, Field, StrictInt, StrictStr

from chaos_agent.application.experiments import ScenarioCatalog, schedule_experiment
from chaos_agent.config import Settings, load_settings
from chaos_agent.domain.experiment import ExperimentRequest

bearer = HTTPBearer(auto_error=False)


class CreateExperiment(BaseModel):
    model_config = ConfigDict(extra="forbid")
    scenario: StrictStr = Field(pattern=r"^[a-z][a-z0-9-]{1,63}$")
    duration_seconds: StrictInt = Field(default=300, ge=1, le=900)
    parameters: dict[str, object] = Field(default_factory=dict)


def create_app(settings: Settings | None = None) -> FastAPI:
    configured = settings or load_settings()
    app = FastAPI(title="Chaos Agent API", version="1")

    def authenticate(
        credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    ) -> str:
        token = configured.api_bearer_token
        if token is None or credentials is None or credentials.scheme.lower() != "bearer":
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="unauthorized")
        if not secrets.compare_digest(credentials.credentials, token):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="unauthorized")
        return "api-operator"

    @app.get("/health")
    def health() -> dict[str, object]:
        return {"status": "ok", "service": "chaos-agent"}

    @app.get("/api/v1/scenarios")
    def scenarios(_: Annotated[str, Depends(authenticate)]) -> dict[str, object]:
        return {"schema_version": 1, "scenarios": ScenarioCatalog().list()}

    @app.post("/api/v1/experiments", status_code=202)
    def create_experiment(
        request: CreateExperiment,
        actor: Annotated[str, Depends(authenticate)],
    ) -> dict[str, object]:
        catalog = ScenarioCatalog()
        if not catalog.contains(request.scenario):
            raise HTTPException(status_code=409, detail="scenario_unavailable")
        target = configured.require_target_access()
        identifier = schedule_experiment(
            configured.data_dir,
            ExperimentRequest(
                target_id=target.target_id,
                target_label=target.target_host,
                scenario_name=request.scenario,
                scenario_version=next(
                    item["version"] for item in catalog.list() if item["name"] == request.scenario
                ),
                parameters=request.parameters,
                requested_duration_seconds=request.duration_seconds,
                initiator=actor,
            ),
            actor=actor,
        )
        return {"schema_version": 1, "experiment_id": identifier, "state": "planned"}

    return app
