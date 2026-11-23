"""marketplace

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-21 02:36:44.019610

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0003"
down_revision: str | Sequence[str] | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "buyer_requests",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("organization", sa.String(length=160), nullable=True),
        sa.Column("phone", sa.String(length=32), nullable=False),
        sa.Column("governorate", sa.String(length=40), nullable=False),
        sa.Column("materials", sa.JSON(), nullable=False),
        sa.Column("thickness_min_mm", sa.Float(), nullable=True),
        sa.Column("thickness_max_mm", sa.Float(), nullable=True),
        sa.Column("min_length_mm", sa.Float(), nullable=True),
        sa.Column("min_width_mm", sa.Float(), nullable=True),
        sa.Column("max_price_tnd_per_kg", sa.Float(), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "listings",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("piece_id", sa.String(length=36), nullable=False),
        sa.Column("workshop_id", sa.String(length=36), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("price_tnd", sa.Float(), nullable=False),
        sa.Column("buyer_request_id", sa.String(length=36), nullable=True),
        sa.Column("sold_price_tnd", sa.Float(), nullable=True),
        sa.Column("fee_tnd", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["buyer_request_id"],
            ["buyer_requests.id"],
        ),
        sa.ForeignKeyConstraint(
            ["piece_id"],
            ["pieces.id"],
        ),
        sa.ForeignKeyConstraint(
            ["workshop_id"],
            ["workshops.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("piece_id"),
    )
    with op.batch_alter_table("listings", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_listings_status"), ["status"], unique=False)
        batch_op.create_index(batch_op.f("ix_listings_workshop_id"), ["workshop_id"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("listings", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_listings_workshop_id"))
        batch_op.drop_index(batch_op.f("ix_listings_status"))

    op.drop_table("listings")
    op.drop_table("buyer_requests")
