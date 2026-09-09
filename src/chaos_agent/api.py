"""Authenticated HTTP adapter for the Chaos Agent application services."""

import secrets
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.responses import HTMLResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, ConfigDict, Field, StrictInt, StrictStr

from chaos_agent.adapters.persistence.database import create_database_engine
from chaos_agent.adapters.persistence.models import Base
from chaos_agent.adapters.persistence.outbox import IntegrationOutbox
from chaos_agent.adapters.persistence.repositories import ExperimentRepository
from chaos_agent.application.experiments import ScenarioCatalog, schedule_experiment
from chaos_agent.config import Settings, load_settings
from chaos_agent.dashboard import DASHBOARD_HTML
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

    @app.get("/", response_class=HTMLResponse, include_in_schema=False)
    def dashboard() -> str:
        return DASHBOARD_HTML

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

    @app.get("/api/v1/experiments")
    def experiments(_: Annotated[str, Depends(authenticate)]) -> dict[str, object]:
        engine = create_database_engine(configured.data_dir / "chaos-agent.db")
        Base.metadata.create_all(engine)
        from sqlalchemy.orm import Session
        with Session(engine) as session:
            rows = ExperimentRepository(session).list_history(limit=100)
            return {"schema_version": 1, "experiments": [
                {"experiment_id": row.experiment_id, "scenario": row.scenario_name,
                 "state": row.state, "expires_at": row.expires_at.isoformat()}
                for row in rows
            ]}

    @app.get("/api/v1/integration/events")
    def integration_events(_: Annotated[str, Depends(authenticate)]) -> dict[str, object]:
        engine = create_database_engine(configured.data_dir / "chaos-agent.db")
        Base.metadata.create_all(engine)
        from sqlalchemy.orm import Session
        with Session(engine) as session:
            events = [row.payload for row in IntegrationOutbox(session).pending()]
            return {"schema_version": 1, "events": events}

    return app
