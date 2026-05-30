"""`QuoteCard` ORM model.

Schema source of truth: `docs/data_model.md` §4.16 (M4 — ISSUE-017
baseline + ISSUE-057 source_kind / tarot / og fields).

One row per session-end "viral asset". A card sources from either a
saju ``reading`` row OR a ``tarot_draws`` row (XOR enforced via the
``source_kind`` discriminator + matching CHECKs). The OG image bake
runs out-of-band — ``og_status`` tracks the pipeline state so the
SSR share endpoint (ISSUE-061) can decide between the baked image and
the fallback static card.

Constraints worth highlighting:

- ``quote_text_max_40_chr_chk`` — application-level CHECK so SQLite
  unit tests can exercise the 40-character cap (FR-018 AC #1).
- ``quote_cards_source_kind_chk`` — ``'reading'`` | ``'tarot'``.
- ``quote_cards_og_status_chk`` — ``'pending'`` | ``'baked'`` | ``'failed'``.
- ``quote_cards_source_*_chk`` — XOR between ``reading_id`` and
  ``tarot_id`` enforced via the discriminator. Postgres CHECK syntax
  works on SQLite too with the same string spelling.
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
    """Shareable quote card surfaced after a reading or tarot session."""

    __tablename__ = "quote_cards"
    __table_args__ = (
        CheckConstraint(
            "LENGTH(quote_text) <= 40",
            name="quote_text_max_40_chr_chk",
        ),
        CheckConstraint(
            "source_kind IN ('reading','tarot')",
            name="quote_cards_source_kind_chk",
        ),
        CheckConstraint(
            "og_status IN ('pending','baked','failed')",
            name="quote_cards_og_status_chk",
        ),
        CheckConstraint(
            "(source_kind = 'reading') = (reading_id IS NOT NULL)",
            name="quote_cards_source_reading_chk",
        ),
        CheckConstraint(
            "(source_kind = 'tarot') = (tarot_id IS NOT NULL)",
            name="quote_cards_source_tarot_chk",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        String(36),
        primary_key=True,
        default=_uuid7_str,
    )
    source_kind: Mapped[str] = mapped_column(
        String,
        nullable=False,
        default="reading",
    )
    reading_id: Mapped[uuid.UUID | None] = mapped_column(
        String(36),
        ForeignKey("readings.id", ondelete="CASCADE"),
        nullable=True,
        unique=True,
    )
    tarot_id: Mapped[uuid.UUID | None] = mapped_column(
        String(36),
        ForeignKey("tarot_draws.id", ondelete="CASCADE"),
        nullable=True,
    )
    quote_text: Mapped[str] = mapped_column(String, nullable=False)
    # Free-form category tag — matches reading.category / tarot card
    # slug at write time but decoupled at the schema level so editorial
    # swaps don't require migrations.
    category: Mapped[str] = mapped_column(String, nullable=False)
    character_key: Mapped[str] = mapped_column(
        String,
        nullable=False,
        default="nuna",
    )
    share_slug: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    og_image_url: Mapped[str | None] = mapped_column(String, nullable=True)
    og_r2_key: Mapped[str | None] = mapped_column(String, nullable=True)
    og_status: Mapped[str] = mapped_column(
        String,
        nullable=False,
        default="pending",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    def __repr__(self) -> str:  # pragma: no cover - debug aid
        return f"<QuoteCard id={self.id} slug={self.share_slug!r}>"
