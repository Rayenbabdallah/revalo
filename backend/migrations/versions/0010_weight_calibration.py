"""weight calibration

Revision ID: 0010
Revises: 0009
Create Date: 2026-11-23 23:18:17.804466

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0010"
down_revision: str | Sequence[str] | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table("pieces", schema=None) as batch_op:
        batch_op.add_column(sa.Column("weight_raw_kg", sa.Float(), nullable=True))

    # Existing estimates were never calibrated: they are the raw values.
    op.execute("UPDATE pieces SET weight_raw_kg = weight_est_kg WHERE weight_raw_kg IS NULL")


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("pieces", schema=None) as batch_op:
        batch_op.drop_column("weight_raw_kg")
