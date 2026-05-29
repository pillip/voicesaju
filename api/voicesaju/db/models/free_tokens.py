"""`FreeToken` ORM model.

Schema source of truth: `docs/data_model.md` §4.7 and §5.5.

Currency for the paywall. One row = one redemption credit.

Constraints worth highlighting:

- **Exactly one owner** — `(user_id IS NULL) <> (device_id IS NULL)`.
- **Idempotent signup grant** — partial unique on
  `(user_id) WHERE kind='signup_grant'` (FR-017 AC).
- **Idempotent non-member trial grant** — partial unique on
  `(device_id) WHERE kind='nonmember_trial'` (FR-003 AC).

The model declares only column-level metadata so SQLite-backed unit tests
can still reflect a sane schema. Postgres-only features (partial unique
indexes) are emitted in the Alembic migration via raw `op.execute`.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from voicesaju.db.base import Base
from voicesaju.db.models.users import uuid7


def _uuid7_str() -> str:
    """Default factory returning a uuidv7 as `str` so SQLite tests bind cleanly.

    SQLAlchemy's `String(36)` column with a `uuid.UUID` Python default
    triggers `Error binding parameter` on aiosqlite (no native UUID
    type). asyncpg in production happily accepts either form, so we
    stringify at the model layer for portability.
    """
    return str(uuid7())


class FreeToken(Base):
    """Free-token ledger row (data_model §4.7)."""

    __tablename__ = "free_tokens"
    __table_args__ = (
        # Application-level CHECK so SQLAlchemy emits it on both Postgres
        # and SQLite. The Postgres migration also emits the same constraint
        # via raw SQL for visibility in `\d free_tokens`.
        CheckConstraint(
            "(user_id IS NULL) <> (device_id IS NULL)",
            name="free_tokens_owner_xor_chk",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        String(36),
        primary_key=True,
        default=_uuid7_str,
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,
    )
    device_id: Mapped[uuid.UUID | None] = mapped_column(
        String(36),
        ForeignKey("devices.id", ondelete="CASCADE"),
        nullable=True,
    )
    # `kind` mirrors the Postgres `free_token_kind_enum` (data_model §4.1):
    # nonmember_trial | signup_grant | failure_compensation | ops_grant.
    # Stored as generic String so SQLite unit tests stay portable; the
    # enum is enforced at the database level on Postgres via the migration
    # which casts inserts through the native enum type.
    kind: Mapped[str] = mapped_column(String, nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    consumed_by_reading_id: Mapped[uuid.UUID | None] = mapped_column(
        String(36),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    def __repr__(self) -> str:  # pragma: no cover - debug aid
        return (
            f"<FreeToken id={self.id} kind={self.kind} "
            f"consumed={self.consumed_at is not None}>"
        )
