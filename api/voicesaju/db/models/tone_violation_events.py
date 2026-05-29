"""`ToneViolationEvent` ORM model.

Schema source of truth: ISSUE-018 (FR-032, NFR-010). One row per
tone-filter trip — used by the safety pipeline to audit "spicy"
responses that breached the active tone policy.

Constraints worth highlighting:

- **At least one parent** — every event must reference either a
  ``Reading`` or a ``TarotDraw`` so the audit trail is traceable. The
  ``tone_violation_events_parent_chk`` CHECK enforces this at the
  application level so SQLite unit tests can exercise it.
- Both ``reading_id`` and ``tarot_id`` are nullable individually — the
  event may originate from either domain.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
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


class ToneViolationEvent(Base):
    """Tone-filter trip event (ISSUE-018)."""

    __tablename__ = "tone_violation_events"
    __table_args__ = (
        CheckConstraint(
            "reading_id IS NOT NULL OR tarot_id IS NOT NULL",
            name="tone_violation_events_parent_chk",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        String(36),
        primary_key=True,
        default=_uuid7_str,
    )
    reading_id: Mapped[uuid.UUID | None] = mapped_column(
        String(36),
        ForeignKey("readings.id", ondelete="CASCADE"),
        nullable=True,
    )
    tarot_id: Mapped[uuid.UUID | None] = mapped_column(
        String(36),
        ForeignKey("tarot_draws.id", ondelete="CASCADE"),
        nullable=True,
    )
    # mild | severe (matches tone_severity_enum in docs/data_model.md).
    severity: Mapped[str] = mapped_column(String, nullable=False)
    # prompt | evalset | filter — which safety layer caught the
    # violation, useful for debugging false-positives.
    layer: Mapped[str] = mapped_column(String, nullable=False)
    evidence_text: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    def __repr__(self) -> str:  # pragma: no cover - debug aid
        return (
            f"<ToneViolationEvent id={self.id} severity={self.severity!r} "
            f"layer={self.layer!r}>"
        )
