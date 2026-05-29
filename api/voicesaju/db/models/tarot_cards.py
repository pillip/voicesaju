"""`TarotCard` ORM model.

Schema source of truth: `docs/data_model.md` tarot-domain section and
ISSUE-016 scope. One row per Major Arcana card (22 total), seeded in
migration ``0008_tarot_tables_seed``.

Highlights:

- ``card_index`` is the natural key (0..21) and is UNIQUE so the seed
  migration can be re-run idempotently via ``ON CONFLICT (card_index)
  DO NOTHING`` on Postgres (mirrored via ``INSERT OR IGNORE`` on
  SQLite).
- ``art_key`` stores a relative R2 object key
  (e.g. ``tarot/major/00.webp``); the actual signing URL is constructed
  at read time so we never persist transient credentials.
- ``meaning_en`` is nullable — Phase-1 launch ships KR copy only; the EN
  translation lands later without a schema change.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from voicesaju.db.base import Base
from voicesaju.db.models.users import uuid7


def _uuid7_str() -> str:
    """Default factory returning a uuidv7 as `str` for aiosqlite compat.

    Mirrors the pattern used by :mod:`voicesaju.db.models.free_tokens`
    and :mod:`voicesaju.db.models.readings` so SQLite-backed unit tests
    bind cleanly to ``String(36)`` columns.
    """
    return str(uuid7())


class TarotCard(Base):
    """Major Arcana card metadata (ISSUE-016)."""

    __tablename__ = "tarot_cards"

    id: Mapped[uuid.UUID] = mapped_column(
        String(36),
        primary_key=True,
        default=_uuid7_str,
    )
    # 0..21 — natural key. UNIQUE so seed migration is idempotent.
    card_index: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        unique=True,
    )
    name_kr: Mapped[str] = mapped_column(String, nullable=False)
    name_en: Mapped[str] = mapped_column(String, nullable=False)
    meaning_kr: Mapped[str] = mapped_column(Text, nullable=False)
    meaning_en: Mapped[str | None] = mapped_column(Text, nullable=True)
    # R2 object key relative path — e.g. "tarot/major/00.webp".
    art_key: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    def __repr__(self) -> str:  # pragma: no cover - debug aid
        return f"<TarotCard idx={self.card_index} name={self.name_en!r}>"
