"""`QuoteCard` ORM model.

Schema source of truth: ISSUE-017 (FR-005). One row per reading — the
shareable "quote card" surfaced after a reading completes. Each card
has a single canonical ``share_slug`` used to build the public share URL
and a length-bounded ``quote_text`` so the rendered Open Graph image
fits the layout reliably.

Constraints worth highlighting:

- ``quote_text_max_40_chr_chk`` — application-level CHECK so SQLite
  unit tests can exercise the 40-character cap.
- ``reading_id`` is UNIQUE (1:1 with ``readings`` row) — every reading
  produces exactly one quote card.
- ``share_slug`` is UNIQUE so the lookup endpoint is O(1).
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from voicesaju.db.base import Base
from voicesaju.db.models.users import uuid7


def _uuid7_str() -> str:
    """Default factory returning a uuidv7 as `str` for aiosqlite compat."""
    return str(uuid7())


class QuoteCard(Base):
    """Shareable quote card surfaced after a reading completes."""

    __tablename__ = "quote_cards"
    __table_args__ = (
        CheckConstraint(
            "LENGTH(quote_text) <= 40",
            name="quote_text_max_40_chr_chk",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        String(36),
        primary_key=True,
        default=_uuid7_str,
    )
    reading_id: Mapped[uuid.UUID] = mapped_column(
        String(36),
        ForeignKey("readings.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    quote_text: Mapped[str] = mapped_column(String, nullable=False)
    # Free-form category tag — matches reading.category at write time but
    # decoupled at the schema level so editorial swaps (e.g. "tarot" ->
    # "daily") don't require migrations.
    category: Mapped[str] = mapped_column(String, nullable=False)
    share_slug: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    og_image_url: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    def __repr__(self) -> str:  # pragma: no cover - debug aid
        return f"<QuoteCard id={self.id} slug={self.share_slug!r}>"
