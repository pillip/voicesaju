"""create payments + subscriptions + refunds tables

Implements `docs/data_model.md` §4.13–§4.15 and §5.9–§5.11.

Strategy:
- Base table DDL is dialect-agnostic so the migration also runs against
  SQLite for unit-style smoke runs (the SQLAlchemy models mirror the same
  shape so `Base.metadata.create_all` works in tests).
- Postgres-only features — partial unique indexes for idempotency
  (`toss_order_id`, `(user_id, idempotency_key)`), and the
  "one active subscription per user" guard — are emitted via raw
  `op.execute()` blocks guarded by `bind.dialect.name == "postgresql"`.

Revision ID: 0006_payments_subscriptions_refunds
Revises: 0005_free_tokens
Create Date: 2026-05-28
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "0006_payments_subscriptions_refunds"
down_revision = "0005_free_tokens"
branch_labels = None
depends_on = None


def _is_postgres() -> bool:
    return op.get_bind().dialect.name == "postgresql"


def upgrade() -> None:
    # --- payments -------------------------------------------------------
    op.create_table(
        "payments",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "user_id",
            sa.String(length=36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # `kind` mirrors `payment_type_enum`; modelled as TEXT here so the
        # migration runs on SQLite too. Postgres-specific cast is applied
        # below via raw SQL.
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("amount_krw", sa.Integer(), nullable=False),
        sa.Column("method", sa.String(), nullable=False),
        sa.Column(
            "status",
            sa.String(),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("toss_order_id", sa.String(), nullable=True),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "refunded_amount_krw",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column("idempotency_key", sa.String(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "amount_krw > 0",
            name="payments_amount_positive_chk",
        ),
        sa.CheckConstraint(
            "refunded_amount_krw >= 0 AND refunded_amount_krw <= amount_krw",
            name="payments_refund_bound_chk",
        ),
    )

    # --- subscriptions --------------------------------------------------
    op.create_table(
        "subscriptions",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "user_id",
            sa.String(length=36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # `status` mirrors `subscription_status_enum`; modelled as TEXT here
        # so the migration runs on SQLite too. Postgres-specific cast is
        # applied below via raw SQL.
        sa.Column("status", sa.String(), nullable=False),
        sa.Column(
            "monthly_saju_remaining",
            sa.Integer(),
            nullable=False,
            server_default="1",
        ),
        sa.Column(
            "current_period_start",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "current_period_end",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("canceled_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "monthly_saju_remaining >= 0 AND monthly_saju_remaining <= 1",
            name="subs_monthly_remaining_chk",
        ),
    )

    # --- refunds --------------------------------------------------------
    op.create_table(
        "refunds",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "payment_id",
            sa.String(length=36),
            sa.ForeignKey("payments.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("amount_krw", sa.Integer(), nullable=False),
        sa.Column("reason", sa.String(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "amount_krw > 0",
            name="refunds_amount_positive_chk",
        ),
    )

    # --- Postgres-only partial unique indexes ---------------------------
    if _is_postgres():
        # Idempotent client-generated checkout order — FR-021 AC.
        op.execute(
            "CREATE UNIQUE INDEX payments_toss_order_id_uk "
            "ON payments (toss_order_id) "
            "WHERE toss_order_id IS NOT NULL"
        )

        # Per-user idempotency for retried checkout calls — FR-021 AC.
        op.execute(
            "CREATE UNIQUE INDEX payments_idempotency_uk "
            "ON payments (user_id, idempotency_key) "
            "WHERE idempotency_key IS NOT NULL"
        )

        # One active subscription per user — FR-022 AC, data_model §4.14.
        op.execute(
            "CREATE UNIQUE INDEX subscriptions_one_active_per_user "
            "ON subscriptions (user_id) "
            "WHERE status = 'active'"
        )


def downgrade() -> None:
    if _is_postgres():
        op.execute("DROP INDEX IF EXISTS subscriptions_one_active_per_user")
        op.execute("DROP INDEX IF EXISTS payments_idempotency_uk")
        op.execute("DROP INDEX IF EXISTS payments_toss_order_id_uk")

    op.drop_table("refunds")
    op.drop_table("subscriptions")
    op.drop_table("payments")
