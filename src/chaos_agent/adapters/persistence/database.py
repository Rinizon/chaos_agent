"""SQLite engine configuration and schema bootstrap."""

from pathlib import Path
from typing import Any

from sqlalchemy import Engine, create_engine, event


def create_database_engine(database_path: Path) -> Engine:
    database_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    engine = create_engine(
        f"sqlite:///{database_path}",
        connect_args={"check_same_thread": False, "timeout": 5},
    )

    @event.listens_for(engine, "connect")
    def configure_sqlite(connection: Any, _record: Any) -> None:
        """Apply SQLite safety pragmas to each pooled connection."""
        # SQLAlchemy supplies a DB-API connection here; keeping the listener
        # typed narrowly avoids leaking a driver-specific type into callers.
        cursor = connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.close()

    return engine
