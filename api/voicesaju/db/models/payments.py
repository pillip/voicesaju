"""`Payment` ORM model.

Schema source of truth: `docs/data_model.md` §4.13 and §5.9.

Each row is a Toss Payments receipt. Card data is **never** persisted
(NFR-006) — we only store the transactional envelope (`toss_order_id`,
status, amount, refund bookkeeping).

Constraints worth highlighting:

- **Positive amount** — `amount_krw > 0`.
- **Refund bookkeeping bounded** — `0 <= refunded_amount_krw <= amount_krw`.
- **Idempotency** — Postgres partial unique indexes on `toss_order_id`
  (when not NULL) and `(user_id, idempotency_key)` (when not NULL) are
  emitted in the Alembic migration via raw SQL guarded by dialect, so
  SQLite-backed unit tests can still bind the schema cleanly.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, func
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


class Payment(Base):
    """Payment row (data_model §4.13)."""

    __tablename__ = "payments"
    __table_args__ = (
        # Application-level CHECKs so SQLAlchemy emits them on both Postgres
        # and SQLite. The Postgres migration also emits the same constraints
        # for visibility in `\d payments`.
        CheckConstraint(
            "amount_krw > 0",
            name="payments_amount_positive_chk",
        ),
        CheckConstraint(
            "refunded_amount_krw >= 0 AND refunded_amount_krw <= amount_krw",
            name="payments_refund_bound_chk",
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
    # `kind` mirrors `payment_type_enum` (single | subscription). Stored as
    # generic String so SQLite unit tests stay portable; the Postgres enum
    # cast is applied via the migration.
    kind: Mapped[str] = mapped_column(String, nullable=False)
    amount_krw: Mapped[int] = mapped_column(Integer, nullable=False)
    # `method` mirrors `payment_method_enum`.
    method: Mapped[str] = mapped_column(String, nullable=False)
    # `status` mirrors `payment_status_enum`. Default `'pending'`.
    status: Mapped[str] = mapped_column(
        String,
        nullable=False,
        default="pending",
        server_default="pending",
    )
    toss_order_id: Mapped[str | None] = mapped_column(String, nullable=True)
    # ``toss_payment_key`` is the Toss-side receipt id, stamped onto the
    # row when the confirm/webhook flow finalises the payment. Used as the
    # idempotency anchor for the ISSUE-045 webhook handler so a duplicate
    # ``PAYMENT_DONE`` delivery is a no-op.
    toss_payment_key: Mapped[str | None] = mapped_column(String, nullable=True)
    paid_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    refunded_amount_krw: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    idempotency_key: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    def __repr__(self) -> str:  # pragma: no cover - debug aid
        return (
            f"<Payment id={self.id} kind={self.kind} "
            f"status={self.status} amount_krw={self.amount_krw}>"
        )
