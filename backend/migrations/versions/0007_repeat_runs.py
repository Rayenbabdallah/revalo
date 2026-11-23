"""repeat runs

Revision ID: 0007
Revises: 0006
Create Date: 2026-11-23 19:21:32.064972

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0007"
down_revision: str | Sequence[str] | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table("jobs", schema=None) as batch_op:
        batch_op.add_column(sa.Column("created_by", sa.String(length=120), nullable=True))
        batch_op.add_column(sa.Column("runs", sa.Integer(), server_default="1", nullable=False))
        batch_op.add_column(sa.Column("repeat_of_id", sa.String(length=36), nullable=True))
        batch_op.create_foreign_key("fk_jobs_repeat_of_id_jobs", "jobs", ["repeat_of_id"], ["id"])

    with op.batch_alter_table("pieces", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("run_index", sa.Integer(), server_default="0", nullable=False)
        )

    # Who uploaded each existing job: the actor of its pieces' "created" events.
    op.execute(
        "UPDATE jobs SET created_by = (SELECT e.actor FROM piece_events e "
        "JOIN pieces p ON p.id = e.piece_id "
        "WHERE p.job_id = jobs.id AND e.action = 'created' LIMIT 1) "
        "WHERE created_by IS NULL"
    )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("pieces", schema=None) as batch_op:
        batch_op.drop_column("run_index")

    with op.batch_alter_table("jobs", schema=None) as batch_op:
        batch_op.drop_constraint("fk_jobs_repeat_of_id_jobs", type_="foreignkey")
        batch_op.drop_column("repeat_of_id")
        batch_op.drop_column("runs")
        batch_op.drop_column("created_by")
