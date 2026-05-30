"""`Subscription` ORM model.

Schema source of truth: `docs/data_model.md` §4.14 and §5.10.

One active subscription per user (current design — v1 doesn't support
multi-tier). `monthly_saju_remaining` enforces FR-022 (1 saju per period).

Constraints worth highlighting:

- **Monthly saju remaining bounded** — `0 <= monthly_saju_remaining <= 1`.
- **At most one active subscription per user** — Postgres-only partial
  unique index on `user_id` `WHERE status='active'` is declared in the
  migration via raw SQL.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from voicesaju.db.base import Base
from voicesaju.db.models.users import uuid7


def _uuid7_str() -> str:
    """Default factory returning a uuidv7 as `str` so SQLite tests bind cleanly."""
    return str(uuid7())


class Subscription(Base):
    """Subscription row (data_model §4.14)."""

    __tablename__ = "subscriptions"
    __table_args__ = (
        CheckConstraint(
            "monthly_saju_remaining >= 0 AND monthly_saju_remaining <= 1",
            name="subs_monthly_remaining_chk",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        String(36),
        primary_key=True,
        default=_uuid7_str,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    # `status` mirrors `subscription_status_enum`. Stored as generic String
    # for SQLite portability; the Postgres enum cast happens in the migration.
    status: Mapped[str] = mapped_column(String, nullable=False)
    monthly_saju_remaining: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        server_default="1",
    )
    current_period_start: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    current_period_end: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    canceled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # ISSUE-068: stamped immediately when the user clicks "구독 해지" so
    # ``cancel_at_period_end`` semantics can be enforced without waiting
    # for the Toss webhook. Distinct from ``canceled_at`` (terminal,
    # written by the SUBSCRIPTION_CANCELED webhook after period_end).
    cancel_requested_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    def __repr__(self) -> str:  # pragma: no cover - debug aid
        return (
            f"<Subscription id={self.id} status={self.status} "
            f"period_end={self.current_period_end}>"
        )
