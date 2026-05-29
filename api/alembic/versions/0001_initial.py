"""initial empty migration

Establishes the `alembic_version` table without creating any application
schema. Concrete enums and tables are added in follow-up migrations
(ISSUE-007 onwards).

Revision ID: 0001_initial
Revises:
Create Date: 2026-05-29
"""

from __future__ import annotations

# revision identifiers, used by Alembic.
revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Initial revision is intentionally a no-op."""
    pass


def downgrade() -> None:
    """No schema to drop."""
    pass
