"""audit_events: minimal table for hard-delete cron event logging (ISSUE-088).

Adds the ``audit_events`` table referenced by the GDPR/PIPA hard-delete
worker. The worker writes one row per user removed (and one per
dependent table cleared) so we have a tamper-evident record of every
PII deletion — required by NFR-005 (GDPR/PIPA right-to-erasure /
right-to-be-forgotten audit trail).

Schema is deliberately small:

- ``id``           — uuidv7 PK (stringified for SQLite portability).
- ``entity_type``  — ``'user' | 'profile' | 'reading' | ...`` etc.
                     Kept as a free-form string so future event types
                     don't require a migration.
- ``entity_id``    — the deleted row's PK as a string. NOT a FK because
                     the referenced row is gone by the time this is
                     read.
- ``event_type``   — ``'hard_delete'`` for ISSUE-088; reserved for
                     future audit events (login, billing-event, etc.).
- ``occurred_at``  — server-stamped UTC timestamp.
- ``payload``      — optional JSON blob with context (e.g. R2 keys
                     removed, dependent row counts). ``JSON`` maps to
                     ``jsonb`` on Postgres and ``TEXT`` on SQLite.

There are intentionally NO foreign keys here — the table is append-only
and must survive its referenced rows being deleted.

Revision ID: 0017_audit_events
Revises: 0016_refunds_status_fields
Create Date: 2026-06-01
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "0017_audit_events"
down_revision = "0016_refunds_status_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "audit_events",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column("entity_type", sa.String(), nullable=False),
        sa.Column("entity_id", sa.String(length=36), nullable=False),
        sa.Column("event_type", sa.String(), nullable=False),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        # ``JSON`` round-trips as TEXT on SQLite and jsonb on Postgres;
        # nullable because some event types may carry no payload.
        sa.Column("payload", sa.JSON(), nullable=True),
    )
    # Index on ``(event_type, occurred_at)`` so the eventual ops dashboard
    # can scan the most recent hard-deletes without a sequential read.
    op.create_index(
        "audit_events_event_type_occurred_at_idx",
        "audit_events",
        ["event_type", "occurred_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "audit_events_event_type_occurred_at_idx",
        table_name="audit_events",
    )
    op.drop_table("audit_events")
