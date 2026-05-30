"""add audio_r2_key to reading_followups (ISSUE-041)

The follow-up answer endpoint reuses the SSE pipeline machinery from
ISSUE-039 (TTS chunks → R2 → SSE), and persists the final per-slot
audio object key on the `reading_followups` row so the replay path
can serve `main.mp3` per follow-up without re-streaming the LLM.

Nullable for backfill compatibility — a row that's been suggested but
not yet answered legitimately has no audio key.

Revision ID: 0013_followup_audio_r2_key
Revises: 0012_reading_audio_metadata
Create Date: 2026-05-30
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "0013_followup_audio_r2_key"
down_revision = "0012_reading_audio_metadata"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("reading_followups") as batch_op:
        batch_op.add_column(sa.Column("audio_r2_key", sa.String(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("reading_followups") as batch_op:
        batch_op.drop_column("audio_r2_key")
