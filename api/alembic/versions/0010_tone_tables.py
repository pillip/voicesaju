"""create tone_prompt_versions + tone_eval_cases + tone_violation_events

Implements ISSUE-018 (FR-032, NFR-010). Three tone-pipeline tables:

- ``tone_prompt_versions`` — versioned safety/system prompts.
  At most one active version per ``prompt_key`` is enforced via the
  Postgres-only partial unique index
  ``tone_prompt_active_singleton_uq`` emitted via raw SQL.
- ``tone_eval_cases`` — labelled test cases for the offline eval suite.
- ``tone_violation_events`` — audit log row whenever the safety
  pipeline trips. Each row must reference at least one of a Reading or
  a TarotDraw via the ``tone_violation_events_parent_chk`` CHECK.

Revision ID: 0010_tone_tables
Revises: 0009_quote_intro_character
Create Date: 2026-05-29
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "0010_tone_tables"
down_revision = "0009_quote_intro_character"
branch_labels = None
depends_on = None


def _is_postgres() -> bool:
    return op.get_bind().dialect.name == "postgresql"


def upgrade() -> None:
    # --- tone_prompt_versions -------------------------------------------
    op.create_table(
        "tone_prompt_versions",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("prompt_key", sa.String(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("prompt_text", sa.Text(), nullable=False),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "LENGTH(prompt_key) > 0",
            name="tone_prompt_versions_key_not_empty_chk",
        ),
    )

    # --- tone_eval_cases ------------------------------------------------
    op.create_table(
        "tone_eval_cases",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("case_kind", sa.String(), nullable=False),
        sa.Column("input_text", sa.Text(), nullable=False),
        sa.Column("expected_label", sa.String(), nullable=False),
        sa.Column("category_tag", sa.String(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    # --- tone_violation_events -----------------------------------------
    op.create_table(
        "tone_violation_events",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "reading_id",
            sa.String(length=36),
            sa.ForeignKey("readings.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column(
            "tarot_id",
            sa.String(length=36),
            sa.ForeignKey("tarot_draws.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("severity", sa.String(), nullable=False),
        sa.Column("layer", sa.String(), nullable=False),
        sa.Column("evidence_text", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "reading_id IS NOT NULL OR tarot_id IS NOT NULL",
            name="tone_violation_events_parent_chk",
        ),
    )

    # --- Postgres-only partial unique index ----------------------------
    if _is_postgres():
        # At most one active version per prompt_key. Modelled as a
        # partial unique so a row can be deactivated (is_active=false)
        # without dropping the audit trail.
        op.execute(
            "CREATE UNIQUE INDEX tone_prompt_active_singleton_uq "
            "ON tone_prompt_versions (prompt_key) "
            "WHERE is_active = true"
        )


def downgrade() -> None:
    if _is_postgres():
        op.execute("DROP INDEX IF EXISTS tone_prompt_active_singleton_uq")

    op.drop_table("tone_violation_events")
    op.drop_table("tone_eval_cases")
    op.drop_table("tone_prompt_versions")
