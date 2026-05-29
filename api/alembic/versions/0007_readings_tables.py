"""create readings + transcripts + followups + audio tables

Implements `docs/data_model.md` §4.8-§4.11 and §5.6-§5.7 (subset scoped
to ISSUE-015 — additional cost / engine / model-version columns will be
backfilled in subsequent migrations as the streaming pipeline lands).

Strategy:

- Base table DDL is dialect-agnostic so the migration runs against
  SQLite for unit-style smoke runs (the SQLAlchemy models mirror the
  same shape so `Base.metadata.create_all` works in tests).
- Postgres-only features — the partial unique index for
  ``reading_followups (reading_id, slot_index)`` — are emitted via raw
  ``op.execute()`` blocks guarded by ``bind.dialect.name == 'postgresql'``.

Revision ID: 0007_readings_tables
Revises: 0006_payments_subscriptions_refunds
Create Date: 2026-05-29
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "0007_readings_tables"
down_revision = "0006_payments_subscriptions_refunds"
branch_labels = None
depends_on = None


def _is_postgres() -> bool:
    return op.get_bind().dialect.name == "postgresql"


def upgrade() -> None:
    # --- readings -------------------------------------------------------
    op.create_table(
        "readings",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "user_id",
            sa.String(length=36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # `category` mirrors `category_enum`; TEXT for SQLite portability.
        sa.Column("category", sa.String(), nullable=False),
        # `status` mirrors `reading_status_enum`.
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("chart_hash", sa.String(length=64), nullable=True),
        sa.Column("character_key", sa.String(), nullable=False),
        sa.Column("idempotency_key", sa.String(), nullable=True),
        sa.Column("entitlement_kind", sa.String(), nullable=False),
        sa.Column(
            "payment_id",
            sa.String(length=36),
            sa.ForeignKey("payments.id"),
            nullable=True,
        ),
        sa.Column(
            "subscription_id",
            sa.String(length=36),
            sa.ForeignKey("subscriptions.id"),
            nullable=True,
        ),
        sa.Column(
            "free_token_id",
            sa.String(length=36),
            sa.ForeignKey("free_tokens.id"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "(entitlement_kind = 'payment' AND payment_id IS NOT NULL) OR "
            "(entitlement_kind = 'subscription' AND subscription_id IS NOT NULL) OR "
            "(entitlement_kind = 'free_token' AND free_token_id IS NOT NULL)",
            name="readings_entitlement_chk",
        ),
    )

    # --- reading_transcripts -------------------------------------------
    op.create_table(
        "reading_transcripts",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "reading_id",
            sa.String(length=36),
            sa.ForeignKey("readings.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("transcript_text", sa.Text(), nullable=False),
        sa.Column("model_name", sa.String(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    # --- reading_followups ---------------------------------------------
    op.create_table(
        "reading_followups",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "reading_id",
            sa.String(length=36),
            sa.ForeignKey("readings.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("slot_index", sa.Integer(), nullable=False),
        sa.Column("question_text", sa.Text(), nullable=False),
        sa.Column("answer_text", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "slot_index >= 0 AND slot_index <= 2",
            name="followups_slot_range_chk",
        ),
    )

    # --- reading_audio --------------------------------------------------
    op.create_table(
        "reading_audio",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "reading_id",
            sa.String(length=36),
            sa.ForeignKey("readings.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("r2_url", sa.String(), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "duration_ms >= 60000 AND duration_ms <= 120000",
            name="audio_duration_chk",
        ),
    )

    # --- Postgres-only partial unique indexes --------------------------
    if _is_postgres():
        # AC: two followups sharing (reading_id, slot_index) must be
        # rejected. Modelled as a partial unique on slot_index so a
        # future "soft-delete" can null the row without losing the guard.
        op.execute(
            "CREATE UNIQUE INDEX reading_followups_reading_slot_uq "
            "ON reading_followups (reading_id, slot_index) "
            "WHERE slot_index IS NOT NULL"
        )


def downgrade() -> None:
    if _is_postgres():
        op.execute("DROP INDEX IF EXISTS reading_followups_reading_slot_uq")

    op.drop_table("reading_audio")
    op.drop_table("reading_followups")
    op.drop_table("reading_transcripts")
    op.drop_table("readings")
