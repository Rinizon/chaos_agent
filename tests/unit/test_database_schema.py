from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config

from chaos_agent.adapters.persistence.database import (
    SchemaCompatibilityError,
    create_database_engine,
    require_current_schema,
)


def migrate(database_path: Path, revision: str = "head") -> None:
    config = Config(str(Path(__file__).parents[2] / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", f"sqlite:///{database_path}")
    command.upgrade(config, revision)


def test_schema_check_refuses_unversioned_database(tmp_path: Path) -> None:
    engine = create_database_engine(tmp_path / "agent.db")
    with pytest.raises(SchemaCompatibilityError, match="revision must be 0004"):
        require_current_schema(engine)


def test_schema_check_accepts_exact_head_revision(tmp_path: Path) -> None:
    database_path = tmp_path / "agent.db"
    migrate(database_path)
    require_current_schema(create_database_engine(database_path))


def test_schema_check_refuses_older_revision(tmp_path: Path) -> None:
    database_path = tmp_path / "agent.db"
    migrate(database_path, "0003")
    with pytest.raises(SchemaCompatibilityError, match="revision must be 0004"):
        require_current_schema(create_database_engine(database_path))
