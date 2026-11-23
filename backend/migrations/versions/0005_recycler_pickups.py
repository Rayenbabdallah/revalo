"""recycler pickups

Revision ID: 0005
Revises: 0004
Create Date: 2026-11-21 11:32:36.766394

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0005"
down_revision: str | Sequence[str] | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "pickups",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("workshop_id", sa.String(length=36), nullable=False),
        sa.Column("recycler_id", sa.String(length=36), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("scheduled_for", sa.Date(), nullable=True),
        sa.Column("estimated_kg", sa.Float(), nullable=False),
        sa.Column("weighed_kg", sa.Float(), nullable=True),
        sa.Column("paid_tnd", sa.Float(), nullable=True),
        sa.Column("created_by", sa.String(length=120), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["recycler_id"],
            ["buyer_requests.id"],
        ),
        sa.ForeignKeyConstraint(
            ["workshop_id"],
            ["workshops.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("pickups", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_pickups_workshop_id"), ["workshop_id"], unique=False)

    op.create_table(
        "pickup_items",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("pickup_id", sa.String(length=36), nullable=False),
        sa.Column("piece_id", sa.String(length=36), nullable=False),
        sa.ForeignKeyConstraint(
            ["pickup_id"],
            ["pickups.id"],
        ),
        sa.ForeignKeyConstraint(
            ["piece_id"],
            ["pieces.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("pickup_items", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_pickup_items_pickup_id"), ["pickup_id"], unique=False)

    with op.batch_alter_table("buyer_requests", schema=None) as batch_op:
        batch_op.add_column(sa.Column("offered_tnd_per_kg", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("min_lot_kg", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("pickup_note", sa.Text(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("buyer_requests", schema=None) as batch_op:
        batch_op.drop_column("pickup_note")
        batch_op.drop_column("min_lot_kg")
        batch_op.drop_column("offered_tnd_per_kg")

    with op.batch_alter_table("pickup_items", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_pickup_items_pickup_id"))

    op.drop_table("pickup_items")
    with op.batch_alter_table("pickups", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_pickups_workshop_id"))

    op.drop_table("pickups")
