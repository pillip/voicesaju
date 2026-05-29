"""create free_tokens table

Implements `docs/data_model.md` §4.7 and §5.5.

Strategy:
- Base table DDL is dialect-agnostic so the migration also runs against
  SQLite for unit-style smoke runs (the SQLAlchemy model mirrors the same
  shape so `Base.metadata.create_all` works in tests).
- Postgres-only features — partial unique indexes for idempotent grants
  (FR-003 / FR-017), partial compound indexes for active-token lookup
  (AP-16 / AP-17) — are emitted via raw `op.execute()` blocks guarded by
  `bind.dialect.name == "postgresql"`.

Revision ID: 0005_free_tokens
Revises: 0004_profiles_saju_charts
Create Date: 2026-05-29
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "0005_free_tokens"
down_revision = "0004_profiles_saju_charts"
branch_labels = None
depends_on = None


def _is_postgres() -> bool:
    return op.get_bind().dialect.name == "postgresql"


def upgrade() -> None:
    # --- free_tokens ----------------------------------------------------
    op.create_table(
        "free_tokens",
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
        # `kind` is a Postgres enum at the DB level; modelled as TEXT here
        # so the migration runs on SQLite too. The Postgres-specific cast
        # to `free_token_kind_enum` is applied below via raw SQL.
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "consumed_by_reading_id",
            sa.String(length=36),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "(user_id IS NULL) <> (device_id IS NULL)",
            name="free_tokens_owner_xor_chk",
        ),
    )

    # --- Postgres-only constraints + partial indexes --------------------
    if _is_postgres():
        # Cast `kind` to the native enum created in 0002_postgres_enums.
        op.execute(
            "ALTER TABLE free_tokens "
            "ALTER COLUMN kind TYPE free_token_kind_enum "
            "USING kind::free_token_kind_enum"
        )

        # data_model §5.5: idempotent signup grant — FR-017 AC.
        op.execute(
            "CREATE UNIQUE INDEX free_tokens_signup_grant_uq "
            "ON free_tokens (user_id) "
            "WHERE kind = 'signup_grant' AND user_id IS NOT NULL"
        )

        # data_model §5.5: idempotent non-member trial grant — FR-003 AC.
        op.execute(
            "CREATE UNIQUE INDEX free_tokens_nonmember_trial_uq "
            "ON free_tokens (device_id) "
            "WHERE kind = 'nonmember_trial' AND device_id IS NOT NULL"
        )

        # AP-16: active-token-for-user lookup.
        op.execute(
            "CREATE INDEX free_tokens_user_active_idx "
            "ON free_tokens (user_id, kind) "
            "WHERE consumed_at IS NULL AND user_id IS NOT NULL"
        )

        # AP-17: active-token-for-device lookup.
        op.execute(
            "CREATE INDEX free_tokens_device_active_idx "
            "ON free_tokens (device_id, kind) "
            "WHERE consumed_at IS NULL AND device_id IS NOT NULL"
        )


def downgrade() -> None:
    if _is_postgres():
        op.execute("DROP INDEX IF EXISTS free_tokens_device_active_idx")
        op.execute("DROP INDEX IF EXISTS free_tokens_user_active_idx")
        op.execute("DROP INDEX IF EXISTS free_tokens_nonmember_trial_uq")
        op.execute("DROP INDEX IF EXISTS free_tokens_signup_grant_uq")

    op.drop_table("free_tokens")
