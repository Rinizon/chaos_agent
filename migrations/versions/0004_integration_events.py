"""add sanitized integration outbox"""
import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table("integration_events",
        sa.Column("event_id", sa.String(36), primary_key=True),
        sa.Column("experiment_id", sa.String(36), nullable=False),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("delivery_state", sa.String(16), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False))


def downgrade() -> None:
    op.drop_table("integration_events")
