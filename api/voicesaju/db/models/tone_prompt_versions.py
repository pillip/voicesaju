"""`TonePromptVersion` ORM model.

Schema source of truth: ISSUE-018 (FR-032, NFR-010). One row per
versioned tone prompt — the system / safety prompt that constrains
the persona's "spicy" replies.

Constraints worth highlighting:

- ``prompt_key`` is bounded to be non-empty via the
  ``tone_prompt_versions_key_not_empty_chk`` CHECK so SQLite unit tests
  can exercise it.
- ``is_active`` defaults to ``False``; the migration emits a
  Postgres-only partial unique index
  ``tone_prompt_active_singleton_uq`` keyed on ``(prompt_key) WHERE
  is_active = true`` so at most one active version exists per
  ``prompt_key``.
- ``activated_at`` is nullable — set when ``is_active`` flips to
  ``True``; kept for audit even after a newer version becomes active.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from voicesaju.db.base import Base
from voicesaju.db.models.users import uuid7


def _uuid7_str() -> str:
    """Default factory returning a uuidv7 as `str` for aiosqlite compat."""
    return str(uuid7())


class TonePromptVersion(Base):
    """Versioned tone-control prompt (ISSUE-018)."""

    __tablename__ = "tone_prompt_versions"
    __table_args__ = (
        CheckConstraint(
            "LENGTH(prompt_key) > 0",
            name="tone_prompt_versions_key_not_empty_chk",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        String(36),
        primary_key=True,
        default=_uuid7_str,
    )
    # Free-form identifier — e.g. "sajununa.system", "tarodosa.spicy".
    prompt_key: Mapped[str] = mapped_column(String, nullable=False)
    # Monotonic integer per prompt_key. Application code enforces the
    # uniqueness of (prompt_key, version); the schema keeps this loose
    # so seed data can backfill historical versions out of order.
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    prompt_text: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=func.cast(False, Boolean),
        default=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    activated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    def __repr__(self) -> str:  # pragma: no cover - debug aid
        return (
            f"<TonePromptVersion key={self.prompt_key!r} v={self.version} "
            f"active={self.is_active}>"
        )
