"""`ReadingTranscript` ORM model.

Schema source of truth: `docs/data_model.md` §4.9.

Persisted text for replay + audit. 1:1 with :class:`Reading`.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from voicesaju.db.base import Base
from voicesaju.db.models.users import uuid7


def _uuid7_str() -> str:
    return str(uuid7())


class ReadingTranscript(Base):
    """One transcript row per reading (data_model §4.9)."""

    __tablename__ = "reading_transcripts"

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
    transcript_text: Mapped[str] = mapped_column(Text, nullable=False)
    model_name: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    def __repr__(self) -> str:  # pragma: no cover - debug aid
        return f"<ReadingTranscript reading_id={self.reading_id}>"
