"""create quote_cards + intro_audio_clips + character_voices + seed

Implements ISSUE-017 (FR-005, FR-018, FR-020). Three content tables
plus baseline seed rows:

- ``character_voices`` — 2 rows (nuna, dosa) with placeholder
  ``tts_voice_id`` values (real ids land during persona-tuning).
- ``intro_audio_clips`` — 6 rows (3 categories × 2 birth-time variants
  × the "nuna" persona; "dosa" launches in M2).
- ``quote_cards`` — empty at migration time; rows are written by the
  reading-complete worker.

The seed inserts use SQLAlchemy parameterised text so the same code
path covers Postgres and SQLite (the SQLite branch of the unit tests
re-runs the seed in-process).

Revision ID: 0009_quote_intro_character
Revises: 0008_tarot_tables_seed
Create Date: 2026-05-29
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "0009_quote_intro_character"
down_revision = "0008_tarot_tables_seed"
branch_labels = None
depends_on = None


_CATEGORIES = ("love", "work", "money")
_VARIANTS = ("known", "unknown")


def _is_postgres() -> bool:
    return op.get_bind().dialect.name == "postgresql"


def upgrade() -> None:
    # --- quote_cards ----------------------------------------------------
    op.create_table(
        "quote_cards",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "reading_id",
            sa.String(length=36),
            sa.ForeignKey("readings.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("quote_text", sa.String(), nullable=False),
        sa.Column("category", sa.String(), nullable=False),
        sa.Column("share_slug", sa.String(), nullable=False, unique=True),
        sa.Column("og_image_url", sa.String(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "LENGTH(quote_text) <= 40",
            name="quote_text_max_40_chr_chk",
        ),
    )

    # --- intro_audio_clips ----------------------------------------------
    op.create_table(
        "intro_audio_clips",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("category", sa.String(), nullable=False),
        sa.Column("birth_time_variant", sa.String(), nullable=False),
        sa.Column("character_key", sa.String(), nullable=False),
        sa.Column("r2_url", sa.String(), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "category",
            "birth_time_variant",
            "character_key",
            name="intro_clips_logical_uq",
        ),
    )

    # --- character_voices -----------------------------------------------
    op.create_table(
        "character_voices",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("character_key", sa.String(), nullable=False, unique=True),
        sa.Column("name_kr", sa.String(), nullable=False),
        sa.Column("tts_voice_id", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    # --- Seed character_voices (2 rows) ---------------------------------
    import uuid as _uuid

    from voicesaju.db.models.users import uuid7

    def _new_id() -> str:
        return str(uuid7()) if _is_postgres() else str(_uuid.uuid4())

    bind = op.get_bind()
    cv_stmt = sa.text(
        "INSERT INTO character_voices "
        "(id, character_key, name_kr, tts_voice_id, description) "
        "VALUES (:id, :character_key, :name_kr, :tts_voice_id, :description)"
    )
    bind.execute(
        cv_stmt,
        {
            "id": _new_id(),
            "character_key": "nuna",
            "name_kr": "시니컬한 누님",
            "tts_voice_id": "TBD_NUNA_VOICE_ID",
            "description": "Mid-30s skeptical Korean female voice",
        },
    )
    bind.execute(
        cv_stmt,
        {
            "id": _new_id(),
            "character_key": "dosa",
            "name_kr": "신비로운 노인 도사",
            "tts_voice_id": "TBD_DOSA_VOICE_ID",
            "description": "Elderly mystical Korean male voice",
        },
    )

    # --- Seed intro_audio_clips (6 rows: 3 cat x 2 variant x nuna) ------
    ic_stmt = sa.text(
        "INSERT INTO intro_audio_clips "
        "(id, category, birth_time_variant, character_key, "
        "r2_url, duration_ms) "
        "VALUES (:id, :category, :birth_time_variant, :character_key, "
        ":r2_url, :duration_ms)"
    )
    for cat in _CATEGORIES:
        for variant in _VARIANTS:
            bind.execute(
                ic_stmt,
                {
                    "id": _new_id(),
                    "category": cat,
                    "birth_time_variant": variant,
                    "character_key": "nuna",
                    "r2_url": f"tts/intro/{cat}/{variant}.mp3",
                    "duration_ms": 15000,
                },
            )


def downgrade() -> None:
    op.drop_table("character_voices")
    op.drop_table("intro_audio_clips")
    op.drop_table("quote_cards")
