"""create users + devices tables

Implements `docs/data_model.md` §4.2, §4.4, §5.1, §5.2.

Strategy:
- Base table DDL is dialect-agnostic so the migration also runs against
  SQLite for unit-style smoke runs (the SQLAlchemy model mirrors the same
  shape so `Base.metadata.create_all` works in tests).
- Postgres-only features — partial unique indexes, the multi-column CHECK
  constraint, partial btree indexes — are emitted via raw `op.execute()`
  blocks guarded by `bind.dialect.name == "postgresql"`. This keeps the
  migration single-source-of-truth while staying portable.

Revision ID: 0003_users_devices
Revises: 0002_postgres_enums
Create Date: 2026-05-29
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "0003_users_devices"
down_revision = "0002_postgres_enums"
branch_labels = None
depends_on = None


def _is_postgres() -> bool:
    return op.get_bind().dialect.name == "postgresql"


def upgrade() -> None:
    # --- users ----------------------------------------------------------
    op.create_table(
        "users",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("kakao_sub", sa.String(), nullable=True),
        sa.Column("apple_sub", sa.String(), nullable=True),
        sa.Column("toss_id", sa.String(), nullable=True),
        sa.Column("email_hash", sa.String(length=64), nullable=True),
        sa.Column(
            "display_locale",
            sa.String(),
            nullable=False,
            server_default="ko-KR",
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
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "kakao_sub IS NOT NULL OR apple_sub IS NOT NULL OR toss_id IS NOT NULL",
            name="users_provider_present_chk",
        ),
    )

    # --- devices --------------------------------------------------------
    op.create_table(
        "devices",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "device_id_client",
            sa.String(),
            nullable=False,
            unique=True,
        ),
        sa.Column(
            "linked_user_id",
            sa.String(length=36),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "first_seen_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "last_seen_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("user_agent_hash", sa.String(length=64), nullable=True),
    )

    # --- Postgres-only partial unique + partial btree indexes ----------
    if _is_postgres():
        # data_model §5.1: users.
        op.execute(
            "CREATE UNIQUE INDEX users_kakao_sub_uq "
            "ON users (kakao_sub) WHERE kakao_sub IS NOT NULL"
        )
        op.execute(
            "CREATE UNIQUE INDEX users_apple_sub_uq "
            "ON users (apple_sub) WHERE apple_sub IS NOT NULL"
        )
        op.execute(
            "CREATE UNIQUE INDEX users_toss_id_uq "
            "ON users (toss_id) WHERE toss_id IS NOT NULL"
        )
        op.execute(
            "CREATE INDEX users_email_hash_idx "
            "ON users (email_hash) WHERE email_hash IS NOT NULL"
        )
        op.execute(
            "CREATE INDEX users_deleted_at_idx "
            "ON users (deleted_at) WHERE deleted_at IS NOT NULL"
        )

        # data_model §5.2: devices. The unique index on device_id_client
        # is already created by SQLAlchemy via the column's `unique=True`,
        # but we rename it for parity with the data_model spec.
        op.execute(
            "ALTER INDEX devices_device_id_client_key RENAME TO devices_client_uq"
        )
        op.execute(
            "CREATE INDEX devices_linked_user_idx "
            "ON devices (linked_user_id) WHERE linked_user_id IS NOT NULL"
        )


def downgrade() -> None:
    if _is_postgres():
        op.execute("DROP INDEX IF EXISTS devices_linked_user_idx")
        op.execute("DROP INDEX IF EXISTS users_deleted_at_idx")
        op.execute("DROP INDEX IF EXISTS users_email_hash_idx")
        op.execute("DROP INDEX IF EXISTS users_toss_id_uq")
        op.execute("DROP INDEX IF EXISTS users_apple_sub_uq")
        op.execute("DROP INDEX IF EXISTS users_kakao_sub_uq")
        # devices_client_uq was renamed from the autoindex — drop the
        # renamed one so a subsequent re-upgrade can recreate it cleanly.
        op.execute("DROP INDEX IF EXISTS devices_client_uq")

    op.drop_table("devices")
    op.drop_table("users")
