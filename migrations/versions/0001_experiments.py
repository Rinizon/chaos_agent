"""create experiment persistence tables

Revision ID: 0001
"""
from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table("experiments", sa.Column("experiment_id", sa.String(36), primary_key=True), sa.Column("target_id", sa.String(36), nullable=False), sa.Column("target_label", sa.String(255), nullable=False), sa.Column("scenario_name", sa.String(64), nullable=False), sa.Column("scenario_version", sa.String(32), nullable=False), sa.Column("parameters", sa.JSON(), nullable=False), sa.Column("requested_duration_seconds", sa.Integer(), nullable=False), sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False), sa.Column("initiator", sa.String(255), nullable=False), sa.Column("state", sa.String(32), nullable=False), sa.Column("revision", sa.Integer(), nullable=False), sa.Column("cleanup_context", sa.JSON()), sa.Column("final_outcome", sa.String(32)), sa.Column("attention_reason", sa.String(256)), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False))
    op.create_table("experiment_transitions", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("experiment_id", sa.String(36), nullable=False), sa.Column("sequence", sa.Integer(), nullable=False), sa.Column("from_state", sa.String(32)), sa.Column("to_state", sa.String(32), nullable=False), sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False), sa.Column("reason", sa.String(64), nullable=False), sa.Column("actor", sa.String(255), nullable=False), sa.Column("revision", sa.Integer(), nullable=False), sa.Column("summary", sa.Text(), nullable=False), sa.UniqueConstraint("experiment_id", "sequence"))
    op.create_index("ix_experiments_state", "experiments", ["state"])
    op.create_index("ix_experiments_expiry", "experiments", ["expires_at"])
    op.create_index("ix_experiments_target_created", "experiments", ["target_id", "created_at"])
    op.create_index("uq_experiments_active_target", "experiments", ["target_id"], unique=True, sqlite_where=sa.text("state NOT IN ('passed','cancelled','failed','operator_attention')"))

def downgrade() -> None:
    op.drop_table("experiment_transitions")
    op.drop_table("experiments")
