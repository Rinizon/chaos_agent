"""SQLAlchemy mappings; repositories expose no ORM objects."""

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Index, Integer, String, Text, UniqueConstraint, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.types import JSON


class Base(DeclarativeBase):
    pass


class ExperimentRow(Base):
    __tablename__ = "experiments"
    __table_args__ = (
        Index("ix_experiments_state", "state"),
        Index("ix_experiments_expiry", "expires_at"),
        Index("ix_experiments_target_created", "target_id", "created_at"),
        Index(
            "uq_experiments_active_target",
            "target_id",
            unique=True,
            sqlite_where=text("state NOT IN ('passed','cancelled','failed','operator_attention')"),
        ),
    )
    experiment_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    target_id: Mapped[str] = mapped_column(String(36), nullable=False)
    target_label: Mapped[str] = mapped_column(String(255), nullable=False)
    scenario_name: Mapped[str] = mapped_column(String(64), nullable=False)
    scenario_version: Mapped[str] = mapped_column(String(32), nullable=False)
    parameters: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    requested_duration_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    initiator: Mapped[str] = mapped_column(String(255), nullable=False)
    state: Mapped[str] = mapped_column(String(32), nullable=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cleanup_context: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    final_outcome: Mapped[str | None] = mapped_column(String(32))
    attention_reason: Mapped[str | None] = mapped_column(String(256))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ExperimentTransitionRow(Base):
    __tablename__ = "experiment_transitions"
    __table_args__ = (UniqueConstraint("experiment_id", "sequence"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    experiment_id: Mapped[str] = mapped_column(String(36), nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    from_state: Mapped[str | None] = mapped_column(String(32))
    to_state: Mapped[str] = mapped_column(String(32), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    reason: Mapped[str] = mapped_column(String(64), nullable=False)
    actor: Mapped[str] = mapped_column(String(255), nullable=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
