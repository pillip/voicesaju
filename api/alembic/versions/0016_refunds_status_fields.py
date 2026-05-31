"""extend refunds with status/reading_id/toss_refund_id/fallback_token_id/finished_at

Implements `docs/data_model.md` §4.15 in full. The original
0006_payments_subscriptions_refunds migration shipped the minimal subset
required for the M2 payment path; the automatic refund worker
(ISSUE-076, FR-023) needs the full schema:

- ``reading_id`` — points back to the failed reading that triggered the
  refund (NULL for ops-initiated refunds).
- ``toss_refund_id`` — Toss-side handle, partial-unique on Postgres so
  webhook deliveries are idempotent.
- ``fallback_token_id`` — set when Toss refund fails and we credited a
  ``failure_compensation`` FreeToken instead.
- ``status`` — ``pending | succeeded | failed_credited | failed_open``.
  Defaults to ``'pending'`` so the retry-worker scan
  (``refunds_status_open_idx``) catches anything still in-flight.
- ``finished_at`` — stamped on terminal transition (succeeded /
  failed_credited / failed_open).

SQLite tests use the same column shape minus the partial-unique index +
``status`` enum cast (both are Postgres-only).

Revision ID: 0016_refunds_status_fields
Revises: 0015_subscriptions_cancel_requested_at
Create Date: 2026-06-01
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "0016_refunds_status_fields"
down_revision = "0015_subscriptions_cancel_requested_at"
branch_labels = None
depends_on = None


def _is_postgres() -> bool:
    return op.get_bind().dialect.name == "postgresql"


def upgrade() -> None:
    # New columns. We add them nullable + with server_default for ``status``
    # so the migration is safe to run against a non-empty production
    # ``refunds`` table — every existing row is back-filled to ``'pending'``
    # automatically.
    op.add_column(
        "refunds",
        sa.Column(
            "reading_id",
            sa.String(length=36),
            sa.ForeignKey("readings.id"),
            nullable=True,
        ),
    )
    op.add_column(
        "refunds",
        sa.Column("toss_refund_id", sa.String(), nullable=True),
    )
    op.add_column(
        "refunds",
        sa.Column(
            "fallback_token_id",
            sa.String(length=36),
            sa.ForeignKey("free_tokens.id"),
            nullable=True,
        ),
    )
    op.add_column(
        "refunds",
        sa.Column(
            "status",
            sa.String(),
            nullable=False,
            server_default="pending",
        ),
    )
    op.add_column(
        "refunds",
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
    )

    # Postgres-only: partial unique on toss_refund_id and the retry-scan
    # partial btree on status — both per data_model §5.11.
    if _is_postgres():
        op.execute(
            "CREATE UNIQUE INDEX refunds_toss_refund_uq "
            "ON refunds (toss_refund_id) "
            "WHERE toss_refund_id IS NOT NULL"
        )
        op.execute(
            "CREATE INDEX refunds_status_open_idx "
            "ON refunds (status) "
            "WHERE status IN ('pending','failed_open')"
        )


def downgrade() -> None:
    if _is_postgres():
        op.execute("DROP INDEX IF EXISTS refunds_status_open_idx")
        op.execute("DROP INDEX IF EXISTS refunds_toss_refund_uq")
    op.drop_column("refunds", "finished_at")
    op.drop_column("refunds", "status")
    op.drop_column("refunds", "fallback_token_id")
    op.drop_column("refunds", "toss_refund_id")
    op.drop_column("refunds", "reading_id")
