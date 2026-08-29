"""add action attempts, control requests, and lease columns"""

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("experiments", sa.Column("owner_instance_id", sa.String(128)))
    op.add_column("experiments", sa.Column("lease_acquired_at", sa.DateTime(timezone=True)))
    op.add_column("experiments", sa.Column("lease_expires_at", sa.DateTime(timezone=True)))
    op.create_table(
        "action_attempts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("experiment_id", sa.String(36), nullable=False),
        sa.Column("action_kind", sa.String(32), nullable=False),
        sa.Column("attempt", sa.Integer(), nullable=False),
        sa.Column("idempotency_key", sa.String(160), nullable=False, unique=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("result_category", sa.String(32), nullable=False),
        sa.Column("evidence", sa.JSON(), nullable=False),
        sa.UniqueConstraint("experiment_id", "action_kind", "attempt"),
    )
    op.create_table(
        "control_requests",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("experiment_id", sa.String(36), nullable=False),
        sa.Column("request_kind", sa.String(32), nullable=False),
        sa.Column("requester", sa.String(255), nullable=False),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("processing_state", sa.String(32), nullable=False),
        sa.Column("idempotency_key", sa.String(160), nullable=False, unique=True),
    )


def downgrade() -> None:
    op.drop_table("control_requests")
    op.drop_table("action_attempts")
    op.drop_column("experiments", "lease_expires_at")
    op.drop_column("experiments", "lease_acquired_at")
    op.drop_column("experiments", "owner_instance_id")
