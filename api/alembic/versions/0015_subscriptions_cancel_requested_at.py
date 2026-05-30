"""subscriptions: add cancel_requested_at (ISSUE-068)

Adds the column that lets ``POST /api/v1/subscriptions/cancel`` stamp a
local timestamp the instant the user clicks "구독 해지", independently
of the Toss webhook that confirms the upstream-side cancellation later
(SUBSCRIPTION_CANCELED → flips ``status='canceled'`` + writes
``canceled_at``).

The new column is nullable on existing rows: any subscription created
before this migration was never user-requested cancel, so ``NULL`` is
the right baseline. The route handler always writes a value alongside
``status='cancel_at_period_end'``, so the application-level invariant
"status='cancel_at_period_end' ↔ cancel_requested_at IS NOT NULL" is
enforced at the route layer (we don't add a CHECK constraint here so
the SQLite test schema stays portable, mirroring ``canceled_at`` from
the original 0006 migration).

Revision ID: 0015_subscriptions_cancel_requested_at
Revises: 0014_quote_cards_source_kind
Create Date: 2026-05-30
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "0015_subscriptions_cancel_requested_at"
down_revision = "0014_quote_cards_source_kind"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ``batch_alter_table`` so SQLite (unit tests) gets a copy-rewrite
    # while Postgres applies the change in-place.
    with op.batch_alter_table("subscriptions") as batch_op:
        batch_op.add_column(
            sa.Column(
                "cancel_requested_at",
                sa.DateTime(timezone=True),
                nullable=True,
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("subscriptions") as batch_op:
        batch_op.drop_column("cancel_requested_at")
