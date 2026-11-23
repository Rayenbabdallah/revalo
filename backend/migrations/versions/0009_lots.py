"""lots

Revision ID: 0009
Revises: 0008
Create Date: 2026-11-23 20:04:35.687187

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0009"
down_revision: str | Sequence[str] | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "lots",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("code", sa.String(length=12), nullable=False),
        sa.Column("workshop_id", sa.String(length=36), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("material_code", sa.String(length=40), nullable=False),
        sa.Column("thickness_mm", sa.Float(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("price_tnd", sa.Float(), nullable=False),
        sa.Column("buyer_request_id", sa.String(length=36), nullable=True),
        sa.Column("sold_price_tnd", sa.Float(), nullable=True),
        sa.Column("fee_tnd", sa.Float(), nullable=True),
        sa.Column("split_from_id", sa.String(length=36), nullable=True),
        sa.Column("created_by", sa.String(length=120), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["buyer_request_id"],
            ["buyer_requests.id"],
        ),
        sa.ForeignKeyConstraint(["split_from_id"], ["lots.id"], name="fk_lots_split_from_id_lots"),
        sa.ForeignKeyConstraint(
            ["workshop_id"],
            ["workshops.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )
    with op.batch_alter_table("lots", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_lots_status"), ["status"], unique=False)
        batch_op.create_index(batch_op.f("ix_lots_workshop_id"), ["workshop_id"], unique=False)

    op.create_table(
        "lot_items",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("lot_id", sa.String(length=36), nullable=False),
        sa.Column("piece_id", sa.String(length=36), nullable=False),
        sa.ForeignKeyConstraint(
            ["lot_id"],
            ["lots.id"],
        ),
        sa.ForeignKeyConstraint(
            ["piece_id"],
            ["pieces.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("lot_items", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_lot_items_lot_id"), ["lot_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_lot_items_piece_id"), ["piece_id"], unique=False)

    with op.batch_alter_table("buyer_requests", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("buys_lots", sa.Boolean(), server_default="0", nullable=False)
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("buyer_requests", schema=None) as batch_op:
        batch_op.drop_column("buys_lots")

    with op.batch_alter_table("lot_items", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_lot_items_piece_id"))
        batch_op.drop_index(batch_op.f("ix_lot_items_lot_id"))

    op.drop_table("lot_items")
    with op.batch_alter_table("lots", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_lots_workshop_id"))
        batch_op.drop_index(batch_op.f("ix_lots_status"))

    op.drop_table("lots")
