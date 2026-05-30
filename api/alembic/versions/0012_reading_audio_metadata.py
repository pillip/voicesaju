"""add r2_key + content_hash + file_size_bytes to reading_audio

ISSUE-038 — the finalize worker writes these columns after stitching
per-sentence chunks into ``main.mp3``. Nullable in this migration so
existing rows from ISSUE-015 stay valid; a future cleanup migration
can backfill + drop nullability once the finalize pipeline has run
against every shipped reading.

Revision ID: 0012_reading_audio_metadata
Revises: 0011_seed_tone_eval_cases
Create Date: 2026-05-30
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0012_reading_audio_metadata"
down_revision = "0011_seed_tone_eval_cases"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Nullable for backfill compatibility — the existing column ``r2_url``
    # already pins the storage URL. Future migration tightens this once
    # every row is finalized through the audio pipeline.
    with op.batch_alter_table("reading_audio") as batch_op:
        batch_op.add_column(sa.Column("r2_key", sa.String(), nullable=True))
        batch_op.add_column(
            sa.Column("content_hash", sa.String(length=64), nullable=True)
        )
        batch_op.add_column(sa.Column("file_size_bytes", sa.Integer(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("reading_audio") as batch_op:
        batch_op.drop_column("file_size_bytes")
        batch_op.drop_column("content_hash")
        batch_op.drop_column("r2_key")
