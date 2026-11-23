"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-11-21 02:05:03.199284

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "workshops",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("governorate", sa.String(length=80), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "jobs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("workshop_id", sa.String(length=36), nullable=False),
        sa.Column("file_name", sa.String(length=255), nullable=False),
        sa.Column("file_format", sa.String(length=20), nullable=False),
        sa.Column("file_sha256", sa.String(length=64), nullable=False),
        sa.Column("file_key", sa.String(length=255), nullable=False),
        sa.Column("material_code", sa.String(length=40), nullable=True),
        sa.Column("thickness_mm", sa.Float(), nullable=True),
        sa.Column("process", sa.String(length=40), nullable=True),
        sa.Column("kerf_mm", sa.Float(), nullable=False),
        sa.Column("sheet_count", sa.Integer(), nullable=False),
        sa.Column("part_count", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("analysis", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approved_by", sa.String(length=120), nullable=True),
        sa.ForeignKeyConstraint(
            ["workshop_id"],
            ["workshops.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("jobs", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_jobs_file_sha256"), ["file_sha256"], unique=False)
        batch_op.create_index(batch_op.f("ix_jobs_workshop_id"), ["workshop_id"], unique=False)

    op.create_table(
        "pieces",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("code", sa.String(length=12), nullable=False),
        sa.Column("job_id", sa.String(length=36), nullable=False),
        sa.Column("workshop_id", sa.String(length=36), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("sheet_index", sa.Integer(), nullable=False),
        sa.Column("label", sa.String(length=20), nullable=False),
        sa.Column("material_code", sa.String(length=40), nullable=True),
        sa.Column("thickness_mm", sa.Float(), nullable=True),
        sa.Column("x_mm", sa.Float(), nullable=True),
        sa.Column("y_mm", sa.Float(), nullable=True),
        sa.Column("width_mm", sa.Float(), nullable=True),
        sa.Column("height_mm", sa.Float(), nullable=True),
        sa.Column("area_m2", sa.Float(), nullable=False),
        sa.Column("weight_est_kg", sa.Float(), nullable=True),
        sa.Column("weight_actual_kg", sa.Float(), nullable=True),
        sa.Column("condition_note", sa.Text(), nullable=True),
        sa.Column("location", sa.String(length=80), nullable=True),
        sa.Column("review_date", sa.Date(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["job_id"],
            ["jobs.id"],
        ),
        sa.ForeignKeyConstraint(
            ["workshop_id"],
            ["workshops.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )
    with op.batch_alter_table("pieces", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_pieces_job_id"), ["job_id"], unique=False)
        batch_op.create_index("ix_pieces_workshop_status", ["workshop_id", "status"], unique=False)

    op.create_table(
        "piece_events",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("piece_id", sa.String(length=36), nullable=False),
        sa.Column("at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("actor", sa.String(length=120), nullable=False),
        sa.Column("action", sa.String(length=40), nullable=False),
        sa.Column("data", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(
            ["piece_id"],
            ["pieces.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("piece_events", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_piece_events_piece_id"), ["piece_id"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("piece_events", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_piece_events_piece_id"))

    op.drop_table("piece_events")
    with op.batch_alter_table("pieces", schema=None) as batch_op:
        batch_op.drop_index("ix_pieces_workshop_status")
        batch_op.drop_index(batch_op.f("ix_pieces_job_id"))

    op.drop_table("pieces")
    with op.batch_alter_table("jobs", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_jobs_workshop_id"))
        batch_op.drop_index(batch_op.f("ix_jobs_file_sha256"))

    op.drop_table("jobs")
    op.drop_table("workshops")
