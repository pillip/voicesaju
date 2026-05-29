"""create profiles + saju_charts tables

Implements `docs/data_model.md` §4.5, §4.6, §5.3, §5.4.

Strategy:
- Base table DDL is dialect-agnostic so the migration also runs against
  SQLite for unit-style smoke runs (the SQLAlchemy models mirror the same
  shapes so `Base.metadata.create_all` works in tests).
- Postgres-only features — partial unique indexes, the JSONB-specific
  CHECK on `pillars->'hour'`, partial btree indexes — are emitted via
  raw `op.execute()` blocks guarded by `bind.dialect.name == "postgresql"`.

Revision ID: 0004_profiles_saju_charts
Revises: 0003_users_devices
Create Date: 2026-05-29
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision = "0004_profiles_saju_charts"
down_revision = "0003_users_devices"
branch_labels = None
depends_on = None


def _is_postgres() -> bool:
    return op.get_bind().dialect.name == "postgresql"


def _json_type() -> sa.types.TypeEngine[object]:
    """Return a JSON column type that prefers JSONB on Postgres."""
    return sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def upgrade() -> None:
    # --- profiles -------------------------------------------------------
    op.create_table(
        "profiles",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "user_id",
            sa.String(length=36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("birth_dt_enc", _json_type(), nullable=False),
        sa.Column(
            "birth_is_lunar",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "birth_time_known",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column("name_optional", sa.String(length=10), nullable=True),
        sa.Column(
            "correction_count",
            sa.SmallInteger(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "correction_count >= 0 AND correction_count <= 2",
            name="profiles_correction_count_chk",
        ),
    )

    # --- saju_charts ----------------------------------------------------
    op.create_table(
        "saju_charts",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "user_id",
            sa.String(length=36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "chart_hash",
            sa.String(length=64),
            nullable=False,
            unique=True,
        ),
        sa.Column("engine_version", sa.String(), nullable=False),
        sa.Column("pillars", _json_type(), nullable=False),
        sa.Column(
            "time_known",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    # --- Postgres-only constraints + partial indexes --------------------
    if _is_postgres():
        # data_model §5.3: profiles.
        # The (user_id) unique already created by SA column.unique. We add
        # a partial btree on deleted_at to mirror the soft-delete pattern
        # already used for users.
        op.execute(
            "CREATE INDEX profiles_deleted_at_idx "
            "ON profiles (deleted_at) WHERE deleted_at IS NOT NULL"
        )

        # data_model §5.4: saju_charts.
        op.execute(
            "CREATE INDEX saju_charts_user_created_idx "
            "ON saju_charts (user_id, created_at DESC)"
        )

        # CHECK: when time_known=true the chart MUST have an hour pillar;
        # when time_known=false the hour pillar MUST be JSON null. The
        # data_model §4.6 notes this is optional ("drop if conflicts with
        # JSONB null semantics"). We use the explicit equality form which
        # works fine with JSONB.
        op.execute(
            "ALTER TABLE saju_charts ADD CONSTRAINT "
            "saju_charts_time_known_chk CHECK ("
            "(time_known = true AND pillars ? 'hour' "
            "AND pillars->'hour' IS NOT NULL) OR "
            "(time_known = false AND ("
            "NOT (pillars ? 'hour') OR pillars->'hour' IS NULL"
            "))"
            ")"
        )


def downgrade() -> None:
    if _is_postgres():
        op.execute(
            "ALTER TABLE saju_charts DROP CONSTRAINT IF EXISTS "
            "saju_charts_time_known_chk"
        )
        op.execute("DROP INDEX IF EXISTS saju_charts_user_created_idx")
        op.execute("DROP INDEX IF EXISTS profiles_deleted_at_idx")

    op.drop_table("saju_charts")
    op.drop_table("profiles")
