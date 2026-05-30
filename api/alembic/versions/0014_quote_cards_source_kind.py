"""extend quote_cards: source_kind, tarot_id, character_key, og_status (ISSUE-057)

Brings the M1 ISSUE-017 ``quote_cards`` schema up to the M4 spec in
data_model.md §4.16. Five additions:

- ``source_kind`` (``'reading'`` | ``'tarot'``) — drives the XOR
  invariant between ``reading_id`` and ``tarot_id``.
- ``tarot_id`` — nullable FK to ``tarot_draws``; the daily-tarot flow
  produces a quote card without a saju reading row.
- ``character_key`` — persona used to produce the quote
  (``'nuna'`` for saju, ``'dosa'`` for tarot at v1; decoupled from
  ``character_voices`` so persona swaps don't require migrations).
- ``og_status`` (``'pending'`` | ``'baked'`` | ``'failed'``) — drives
  the arq ``og_bake`` worker poll loop (ISSUE-058).
- ``og_r2_key`` — filled by the worker after a successful bake.
- ``expires_at`` — A-07 retention; NULL = indefinite v1.

Also drops the now-redundant ``reading_id NOT NULL`` constraint by
recreating the FK as nullable; the XOR check enforces the new shape.

Existing rows (currently zero — `quote_cards` is written by the
session-end worker and the worker isn't wired yet) get
``source_kind = 'reading'`` defensively so the CHECK passes if the
table happened to be populated mid-deploy. Safe because the M1
schema required ``reading_id NOT NULL``.

Revision ID: 0014_quote_cards_source_kind
Revises: 0013_followup_audio_r2_key
Create Date: 2026-05-30
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "0014_quote_cards_source_kind"
down_revision = "0013_followup_audio_r2_key"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ``batch_alter_table`` so SQLite (unit tests) gets a copy-rewrite
    # while Postgres applies the changes in-place. The named FK below
    # mirrors the existing ``readings(id)`` style so downgrades remain
    # symmetric.
    with op.batch_alter_table("quote_cards") as batch_op:
        # `source_kind` first so the CHECK we add later can reference
        # it. Server-default 'reading' for safety on any extant rows.
        batch_op.add_column(
            sa.Column(
                "source_kind",
                sa.String(),
                nullable=False,
                server_default="reading",
            )
        )
        batch_op.add_column(
            sa.Column(
                "tarot_id",
                sa.String(length=36),
                sa.ForeignKey(
                    "tarot_draws.id",
                    name="fk_quote_cards_tarot_id_tarot_draws",
                    ondelete="CASCADE",
                ),
                nullable=True,
            )
        )
        batch_op.add_column(
            sa.Column(
                "character_key",
                sa.String(),
                nullable=False,
                server_default="nuna",
            )
        )
        batch_op.add_column(
            sa.Column(
                "og_status",
                sa.String(),
                nullable=False,
                server_default="pending",
            )
        )
        batch_op.add_column(
            sa.Column(
                "og_r2_key",
                sa.String(),
                nullable=True,
            )
        )
        batch_op.add_column(
            sa.Column(
                "expires_at",
                sa.DateTime(timezone=True),
                nullable=True,
            )
        )

        # Make `reading_id` nullable — XOR with `tarot_id` is enforced
        # below via CHECK.
        batch_op.alter_column(
            "reading_id",
            existing_type=sa.String(length=36),
            nullable=True,
        )

        # XOR + value-domain CHECKs. Names match the data_model.md
        # §4.16 spec so logs are greppable across migrations.
        batch_op.create_check_constraint(
            "quote_cards_source_kind_chk",
            "source_kind IN ('reading','tarot')",
        )
        batch_op.create_check_constraint(
            "quote_cards_og_status_chk",
            "og_status IN ('pending','baked','failed')",
        )
        batch_op.create_check_constraint(
            "quote_cards_source_reading_chk",
            "(source_kind = 'reading') = (reading_id IS NOT NULL)",
        )
        batch_op.create_check_constraint(
            "quote_cards_source_tarot_chk",
            "(source_kind = 'tarot') = (tarot_id IS NOT NULL)",
        )


def downgrade() -> None:
    with op.batch_alter_table("quote_cards") as batch_op:
        batch_op.drop_constraint("quote_cards_source_tarot_chk", type_="check")
        batch_op.drop_constraint("quote_cards_source_reading_chk", type_="check")
        batch_op.drop_constraint("quote_cards_og_status_chk", type_="check")
        batch_op.drop_constraint("quote_cards_source_kind_chk", type_="check")
        batch_op.alter_column(
            "reading_id",
            existing_type=sa.String(length=36),
            nullable=False,
        )
        batch_op.drop_column("expires_at")
        batch_op.drop_column("og_r2_key")
        batch_op.drop_column("og_status")
        batch_op.drop_column("character_key")
        batch_op.drop_column("tarot_id")
        batch_op.drop_column("source_kind")
