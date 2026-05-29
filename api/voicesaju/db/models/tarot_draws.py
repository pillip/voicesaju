"""`TarotDraw` ORM model.

Schema source of truth: `docs/data_model.md` tarot-domain section and
ISSUE-016 scope. One row per daily tarot card draw — by either a logged
in user or a non-member device.

Constraints worth highlighting:

- **Exactly one owner** — ``(user_id IS NULL) <> (device_id IS NULL)``
  enforced via the application-level
  ``tarot_draws_owner_xor_chk`` CHECK so SQLite unit tests can exercise
  it.
- **One draw per owner per day** — partial unique indexes on
  ``(user_id, date_kst) WHERE user_id IS NOT NULL`` and
  ``(device_id, date_kst) WHERE device_id IS NOT NULL`` (Postgres only,
  emitted via raw SQL in the migration).
- ``card_index`` is denormalized from ``tarot_cards.card_index`` so the
  daily-summary endpoint can short-circuit lookups without joining.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from voicesaju.db.base import Base
from voicesaju.db.models.users import uuid7


def _uuid7_str() -> str:
    """Default factory returning a uuidv7 as `str` for aiosqlite compat."""
    return str(uuid7())


class TarotDraw(Base):
    """Daily tarot draw record (ISSUE-016)."""

    __tablename__ = "tarot_draws"
    __table_args__ = (
        # Exactly one owner — application-level CHECK mirrors
        # `free_tokens_owner_xor_chk` so both Postgres and SQLite enforce
        # the rule at write time.
        CheckConstraint(
            "(user_id IS NULL) <> (device_id IS NULL)",
            name="tarot_draws_owner_xor_chk",
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
    card_id: Mapped[uuid.UUID] = mapped_column(
        String(36),
        ForeignKey("tarot_cards.id"),
        nullable=False,
    )
    # Denormalized from tarot_cards.card_index for cheap daily lookups.
    card_index: Mapped[int] = mapped_column(Integer, nullable=False)
    # KST calendar date — paired with owner_id in the daily-uniqueness
    # partial indexes emitted by the migration on Postgres.
    date_kst: Mapped[date] = mapped_column(Date, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    def __repr__(self) -> str:  # pragma: no cover - debug aid
        return (
            f"<TarotDraw id={self.id} card_index={self.card_index} "
            f"date={self.date_kst}>"
        )
