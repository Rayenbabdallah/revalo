"""workshop price book

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-21 02:20:49.432666

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0002"
down_revision: str | Sequence[str] | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "price_entries",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("workshop_id", sa.String(length=36), nullable=False),
        sa.Column("material_code", sa.String(length=40), nullable=False),
        sa.Column("new_tnd_per_kg", sa.Float(), nullable=False),
        sa.Column("scrap_tnd_per_kg", sa.Float(), nullable=False),
        sa.Column("resale_factor", sa.Float(), nullable=False),
        sa.Column("source", sa.Text(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_by", sa.String(length=120), nullable=False),
        sa.ForeignKeyConstraint(
            ["workshop_id"],
            ["workshops.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("workshop_id", "material_code"),
    )
    with op.batch_alter_table("price_entries", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_price_entries_workshop_id"), ["workshop_id"], unique=False
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("price_entries", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_price_entries_workshop_id"))

    op.drop_table("price_entries")
