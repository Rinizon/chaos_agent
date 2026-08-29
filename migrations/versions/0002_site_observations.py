"""add bounded website observation audit rows"""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "site_observations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("experiment_id", sa.String(36), nullable=False),
        sa.Column("phase", sa.String(16), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("available", sa.Boolean(), nullable=False),
        sa.Column("status_code", sa.Integer()),
        sa.Column("duration_ms", sa.Integer()),
        sa.Column("content_matched", sa.Boolean()),
        sa.Column("failure_category", sa.String(64)),
        sa.UniqueConstraint("experiment_id", "phase", "sequence"),
    )


def downgrade() -> None:
    op.drop_table("site_observations")
