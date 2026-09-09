"""Small application services used by the Phase 3 CLI adapters."""

from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy.orm import Session

from chaos_agent.adapters.persistence.database import create_database_engine
from chaos_agent.adapters.persistence.models import Base
from chaos_agent.adapters.persistence.repositories import ExperimentRepository
from chaos_agent.domain.experiment import ExperimentRequest, calculate_expiry


class ScenarioCatalog:
    """Closed production catalog for reviewed scenarios."""

    def list(self) -> list[dict[str, str]]:
        from chaos_agent.application.scenarios.apache_stop import ApacheStopScenario
        from chaos_agent.application.scenarios.cpu_pressure import CpuPressureScenario

        return [{
            "name": ApacheStopScenario.name,
            "version": ApacheStopScenario.version,
            "description": ApacheStopScenario.description,
        }, {
            "name": CpuPressureScenario.name,
            "version": CpuPressureScenario.version,
            "description": CpuPressureScenario.description,
        }]

    def contains(self, name: str) -> bool:
        return any(item["name"] == name for item in self.list())


def schedule_experiment(data_dir: Path, request: ExperimentRequest, *, actor: str) -> str:
    engine = create_database_engine(data_dir / "chaos-agent.db")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        identifier = ExperimentRepository(session).schedule(
            request,
            calculate_expiry(datetime.now(UTC), request.requested_duration_seconds),
            actor=actor,
        )
        session.commit()
        return str(identifier)
