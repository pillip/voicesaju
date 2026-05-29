"""`Reading` ORM model.

Schema source of truth: `docs/data_model.md` §4.8 and §5.6.

One row per saju reading session — paid, subscription-redeemed, or
free-token-unlocked. The model intentionally pulls only the subset of
columns required for the M1 foundation (per ISSUE-015 scope); the
remaining cost / engine / model-version columns documented in §4.8 will
be added in subsequent migrations as the streaming pipeline lands.

Constraints worth highlighting:

- **Entitlement consistency** — exactly one of ``payment_id``,
  ``subscription_id``, ``free_token_id`` must be set, matched to
  ``entitlement_kind``. Enforced via the application-level
  ``readings_entitlement_chk`` CHECK so SQLite-backed unit tests can
  exercise it.
- **Per-user history** — the partial unique index on
  ``(reading_id, slot_index)`` (Postgres-only, emitted via raw SQL in the
  migration) is documented on :class:`ReadingFollowup`.
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

    Mirrors the helper used by :mod:`voicesaju.db.models.payments` —
    aiosqlite cannot bind a ``uuid.UUID`` instance to a ``String(36)``
    column, so we stringify at the model layer for portability.
    """

    return str(uuid7())


class Reading(Base):
    """Saju reading session (data_model §4.8)."""

    __tablename__ = "readings"
    __table_args__ = (
        # Entitlement consistency: exactly the (kind, *_id) pair must agree.
        # The data_model spec lists three separate CHECKs; we collapse them
        # into one disjunction so a single named constraint covers all
        # branches (easier to surface in error messages and to test).
        CheckConstraint(
            "(entitlement_kind = 'payment' AND payment_id IS NOT NULL) OR "
            "(entitlement_kind = 'subscription' AND subscription_id IS NOT NULL) OR "
            "(entitlement_kind = 'free_token' AND free_token_id IS NOT NULL)",
            name="readings_entitlement_chk",
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
    # `category` mirrors `category_enum` (love | work | money | tarot).
    # Stored as generic String for SQLite portability; Postgres enforces
    # the enum type via the migration.
    category: Mapped[str] = mapped_column(String, nullable=False)
    # `status` mirrors `reading_status_enum`
    # (pending | streaming | complete | failed | refunded).
    status: Mapped[str] = mapped_column(String, nullable=False)
    # `chart_hash` references `saju_charts.chart_hash` but we do not
    # enforce a FK because the saju engine is a pure function (no DB row
    # exists until/unless the chart is cached). Cache hits join via this
    # column.
    chart_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # `character_key` mirrors the persona key (sajununa | tarodosa).
    character_key: Mapped[str] = mapped_column(String, nullable=False)
    idempotency_key: Mapped[str | None] = mapped_column(String, nullable=True)
    # `entitlement_kind` enum: payment | subscription | free_token.
    entitlement_kind: Mapped[str] = mapped_column(String, nullable=False)
    payment_id: Mapped[uuid.UUID | None] = mapped_column(
        String(36),
        ForeignKey("payments.id"),
        nullable=True,
    )
    subscription_id: Mapped[uuid.UUID | None] = mapped_column(
        String(36),
        ForeignKey("subscriptions.id"),
        nullable=True,
    )
    free_token_id: Mapped[uuid.UUID | None] = mapped_column(
        String(36),
        ForeignKey("free_tokens.id"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    def __repr__(self) -> str:  # pragma: no cover - debug aid
        return (
            f"<Reading id={self.id} category={self.category} "
            f"status={self.status} entitlement={self.entitlement_kind}>"
        )
