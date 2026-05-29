"""create tarot_cards + tarot_draws tables and seed 22 Major Arcana cards

Implements ISSUE-016. Mirrors ISSUE-015's dialect-aware strategy:

- Base table DDL is dialect-agnostic so the migration runs against
  SQLite for unit-style smoke runs.
- Postgres-only features — the partial unique indexes for
  ``(user_id, date_kst)`` and ``(device_id, date_kst)`` — are emitted via
  ``op.execute`` guarded by ``_is_postgres()``.
- Seed inserts use raw VALUES so the same code path covers both engines.
  On Postgres we add ``ON CONFLICT (card_index) DO NOTHING`` so reruns
  stay idempotent; on SQLite we use ``INSERT OR IGNORE`` to achieve the
  same effect.

Revision ID: 0008_tarot_tables_seed
Revises: 0007_readings_tables
Create Date: 2026-05-29
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "0008_tarot_tables_seed"
down_revision = "0007_readings_tables"
branch_labels = None
depends_on = None


def _is_postgres() -> bool:
    return op.get_bind().dialect.name == "postgresql"


# 22 Major Arcana — (card_index, name_en, name_kr, meaning_kr, meaning_en).
# Meanings are short single-line summaries; the long-form copy lives in
# the content service and is keyed by ``card_index``.
_MAJOR_ARCANA: list[tuple[int, str, str, str, str]] = [
    (
        0,
        "The Fool",
        "바보",
        "새로운 시작과 자유로운 모험.",
        "New beginnings, free spirit.",
    ),
    (1, "The Magician", "마법사", "의지와 창조의 힘.", "Willpower and manifestation."),
    (
        2,
        "The High Priestess",
        "여사제",
        "직관과 숨겨진 지혜.",
        "Intuition and hidden knowledge.",
    ),
    (
        3,
        "The Empress",
        "여황제",
        "풍요와 모성의 사랑.",
        "Abundance and nurturing love.",
    ),
    (4, "The Emperor", "황제", "질서와 권위의 안정.", "Authority and structure."),
    (5, "The Hierophant", "교황", "전통과 가르침의 길.", "Tradition and guidance."),
    (6, "The Lovers", "연인", "사랑과 중요한 선택.", "Love and meaningful choice."),
    (
        7,
        "The Chariot",
        "전차",
        "결단과 전진의 의지.",
        "Determination and forward drive.",
    ),
    (8, "Strength", "힘", "용기와 부드러운 통제.", "Courage and gentle control."),
    (9, "The Hermit", "은둔자", "내면의 탐구와 고독.", "Introspection and solitude."),
    (
        10,
        "Wheel of Fortune",
        "운명의 수레바퀴",
        "변화와 운명의 흐름.",
        "Change and fate.",
    ),
    (11, "Justice", "정의", "공정함과 균형의 판단.", "Fairness and balance."),
    (
        12,
        "The Hanged Man",
        "거꾸로 매달린 사람",
        "관점의 전환과 기다림.",
        "Shifting perspective.",
    ),
    (13, "Death", "죽음", "끝맺음과 새로운 시작.", "Endings and transformation."),
    (14, "Temperance", "절제", "조화와 균형의 융합.", "Harmony and moderation."),
    (15, "The Devil", "악마", "유혹과 속박의 그림자.", "Temptation and bondage."),
    (16, "The Tower", "탑", "급격한 변화와 깨달음.", "Sudden upheaval."),
    (17, "The Star", "별", "희망과 영감의 빛.", "Hope and inspiration."),
    (18, "The Moon", "달", "불안과 무의식의 환상.", "Illusion and uncertainty."),
    (19, "The Sun", "태양", "기쁨과 성공의 활력.", "Joy and vitality."),
    (20, "Judgement", "심판", "각성과 새로운 부름.", "Awakening and renewal."),
    (21, "The World", "세계", "완성과 성취의 순환.", "Completion and fulfilment."),
]


def upgrade() -> None:
    # --- tarot_cards ----------------------------------------------------
    op.create_table(
        "tarot_cards",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("card_index", sa.Integer(), nullable=False, unique=True),
        sa.Column("name_kr", sa.String(), nullable=False),
        sa.Column("name_en", sa.String(), nullable=False),
        sa.Column("meaning_kr", sa.Text(), nullable=False),
        sa.Column("meaning_en", sa.Text(), nullable=True),
        sa.Column("art_key", sa.String(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    # --- tarot_draws ----------------------------------------------------
    op.create_table(
        "tarot_draws",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "user_id",
            sa.String(length=36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column(
            "device_id",
            sa.String(length=36),
            sa.ForeignKey("devices.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column(
            "card_id",
            sa.String(length=36),
            sa.ForeignKey("tarot_cards.id"),
            nullable=False,
        ),
        sa.Column("card_index", sa.Integer(), nullable=False),
        sa.Column("date_kst", sa.Date(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "(user_id IS NULL) <> (device_id IS NULL)",
            name="tarot_draws_owner_xor_chk",
        ),
    )

    # --- Seed 22 Major Arcana cards -------------------------------------
    # uuidv7 ids are generated at insert time per dialect to keep the
    # migration deterministic for tests.
    import uuid as _uuid

    from voicesaju.db.models.users import uuid7

    rows = [
        {
            "id": str(uuid7()) if _is_postgres() else str(_uuid.uuid4()),
            "card_index": idx,
            "name_kr": name_kr,
            "name_en": name_en,
            "meaning_kr": meaning_kr,
            "meaning_en": meaning_en,
            "art_key": f"tarot/major/{idx:02d}.webp",
        }
        for idx, name_en, name_kr, meaning_kr, meaning_en in _MAJOR_ARCANA
    ]

    # Issue one parameterised INSERT per row. SQLAlchemy's ``executemany``
    # path keeps this fast (22 rows) while sidestepping the per-row alias
    # gymnastics that an in-list INSERT would require.
    bind = op.get_bind()
    if _is_postgres():
        stmt = sa.text(
            "INSERT INTO tarot_cards "
            "(id, card_index, name_kr, name_en, "
            "meaning_kr, meaning_en, art_key) "
            "VALUES (:id, :card_index, :name_kr, :name_en, "
            ":meaning_kr, :meaning_en, :art_key) "
            "ON CONFLICT (card_index) DO NOTHING"
        )
    else:
        # SQLite: ``INSERT OR IGNORE`` mirrors ON CONFLICT DO NOTHING
        # because card_index has a UNIQUE constraint.
        stmt = sa.text(
            "INSERT OR IGNORE INTO tarot_cards "
            "(id, card_index, name_kr, name_en, "
            "meaning_kr, meaning_en, art_key) "
            "VALUES (:id, :card_index, :name_kr, :name_en, "
            ":meaning_kr, :meaning_en, :art_key)"
        )
    for row in rows:
        bind.execute(stmt, row)

    # --- Postgres-only partial unique indexes ---------------------------
    if _is_postgres():
        # One draw per user per KST day.
        op.execute(
            "CREATE UNIQUE INDEX tarot_draws_user_date_uq "
            "ON tarot_draws (user_id, date_kst) "
            "WHERE user_id IS NOT NULL"
        )
        # One draw per device per KST day.
        op.execute(
            "CREATE UNIQUE INDEX tarot_draws_device_date_uq "
            "ON tarot_draws (device_id, date_kst) "
            "WHERE device_id IS NOT NULL"
        )


def downgrade() -> None:
    if _is_postgres():
        op.execute("DROP INDEX IF EXISTS tarot_draws_device_date_uq")
        op.execute("DROP INDEX IF EXISTS tarot_draws_user_date_uq")

    op.drop_table("tarot_draws")
    op.drop_table("tarot_cards")
