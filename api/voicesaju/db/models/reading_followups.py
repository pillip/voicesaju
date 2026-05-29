"""`ReadingFollowup` ORM model.

Schema source of truth: `docs/data_model.md` §4.10 and §5.7.

Each follow-up Q+A. Up to 3 per reading (FR-009). ``slot_index`` is
constrained to ``[0, 2]`` so the LLM-suggested button position stays
deterministic.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from voicesaju.db.base import Base
from voicesaju.db.models.users import uuid7


def _uuid7_str() -> str:
    return str(uuid7())


class ReadingFollowup(Base):
    """One follow-up Q+A slot per reading (data_model §4.10)."""

    __tablename__ = "reading_followups"
    __table_args__ = (
        # AC: `slot_index BETWEEN 0 AND 2` — 3 slots per reading (FR-009).
        CheckConstraint(
            "slot_index >= 0 AND slot_index <= 2",
            name="followups_slot_range_chk",
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
    )
    slot_index: Mapped[int] = mapped_column(Integer, nullable=False)
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    answer_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    def __repr__(self) -> str:  # pragma: no cover - debug aid
        return f"<ReadingFollowup reading_id={self.reading_id} slot={self.slot_index}>"
