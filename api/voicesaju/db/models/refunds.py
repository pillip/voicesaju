"""`Refund` ORM model.

Schema source of truth: `docs/data_model.md` §4.15 and §5.11.

Auditable log of refund events (FR-023). One row per refund event;
v1 only issues full refunds but the schema supports partial in theory.

The extended status/finished_at/toss_refund_id/fallback_token_id columns
land via migration `0016_refunds_status_fields` (ISSUE-076). The earlier
M2 migration (`0006_payments_subscriptions_refunds`) only created the
minimal subset; the automatic refund worker needs the full schema so the
retry-scan partial index (`refunds_status_open_idx`) and the Toss-side
idempotency anchor (`refunds_toss_refund_uq`) are both honoured.

Constraints worth highlighting:

- **Positive amount** — `amount_krw > 0`.
- **Status enum** — `status IN ('pending','succeeded','failed_credited','failed_open')`.
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


class Refund(Base):
    """Refund row (data_model §4.15)."""

    __tablename__ = "refunds"
    __table_args__ = (
        CheckConstraint(
            "amount_krw > 0",
            name="refunds_amount_positive_chk",
        ),
        CheckConstraint(
            "status IN ('pending','succeeded','failed_credited','failed_open')",
            name="refunds_status_chk",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        String(36),
        primary_key=True,
        default=_uuid7_str,
    )
    payment_id: Mapped[uuid.UUID] = mapped_column(
        String(36),
        ForeignKey("payments.id", ondelete="CASCADE"),
        nullable=False,
    )
    reading_id: Mapped[uuid.UUID | None] = mapped_column(
        String(36),
        ForeignKey("readings.id"),
        nullable=True,
    )
    amount_krw: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str] = mapped_column(String, nullable=False)
    toss_refund_id: Mapped[str | None] = mapped_column(String, nullable=True)
    fallback_token_id: Mapped[uuid.UUID | None] = mapped_column(
        String(36),
        ForeignKey("free_tokens.id"),
        nullable=True,
    )
    # `status` mirrors `refund_status_enum` (data_model §4.1):
    # pending | succeeded | failed_credited | failed_open.
    status: Mapped[str] = mapped_column(
        String,
        nullable=False,
        default="pending",
        server_default="pending",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    def __repr__(self) -> str:  # pragma: no cover - debug aid
        return (
            f"<Refund id={self.id} payment_id={self.payment_id} "
            f"status={self.status} amount_krw={self.amount_krw}>"
        )
