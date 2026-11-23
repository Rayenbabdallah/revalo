"""planned jobs

Revision ID: 0008
Revises: 0007
Create Date: 2026-11-23 19:49:11.218631

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0008"
down_revision: str | Sequence[str] | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "planned_jobs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("workshop_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("material_code", sa.String(length=40), nullable=False),
        sa.Column("thickness_mm", sa.Float(), nullable=False),
        sa.Column("kerf_mm", sa.Float(), nullable=False),
        sa.Column("parts", sa.JSON(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("created_by", sa.String(length=120), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["workshop_id"],
            ["workshops.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("planned_jobs", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_planned_jobs_workshop_id"), ["workshop_id"], unique=False
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("planned_jobs", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_planned_jobs_workshop_id"))

    op.drop_table("planned_jobs")
