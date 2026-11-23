"""supply offers

Revision ID: 0011
Revises: 0010
Create Date: 2026-11-24 10:12:40.118230

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0011"
down_revision: str | Sequence[str] | None = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "supply_offers",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("workshop_id", sa.String(length=36), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("source", sa.String(length=20), nullable=False),
        sa.Column("seller_name", sa.String(length=120), nullable=False),
        sa.Column("organization", sa.String(length=160), nullable=True),
        sa.Column("phone", sa.String(length=32), nullable=False),
        sa.Column("governorate", sa.String(length=40), nullable=False),
        sa.Column("material_code", sa.String(length=40), nullable=False),
        sa.Column("thickness_mm", sa.Float(), nullable=False),
        sa.Column("width_mm", sa.Float(), nullable=False),
        sa.Column("height_mm", sa.Float(), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("price_tnd", sa.Float(), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("bought_price_tnd", sa.Float(), nullable=True),
        sa.Column("intake_job_id", sa.String(length=36), nullable=True),
        sa.Column("closed_by", sa.String(length=120), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["intake_job_id"], ["jobs.id"]),
        sa.ForeignKeyConstraint(["workshop_id"], ["workshops.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("supply_offers", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_supply_offers_status"), ["status"], unique=False)
        batch_op.create_index(
            batch_op.f("ix_supply_offers_workshop_id"), ["workshop_id"], unique=False
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("supply_offers", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_supply_offers_workshop_id"))
        batch_op.drop_index(batch_op.f("ix_supply_offers_status"))
    op.drop_table("supply_offers")
