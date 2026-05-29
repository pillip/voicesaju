"""`IntroAudioClip` ORM model.

Schema source of truth: ISSUE-017 (FR-018). One row per pre-rendered
intro audio clip — the short audio the persona plays before the LLM
streaming begins.

The logical key is the triple ``(category, birth_time_variant,
character_key)`` so the runtime can pick the right clip with a single
indexed lookup. The seed migration inserts the M1 baseline of 6 clips
(3 categories × 2 birth-time variants × the "nuna" persona). The
"dosa" persona launches in M2 and will reuse the same uniqueness key.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    DateTime,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from voicesaju.db.base import Base
from voicesaju.db.models.users import uuid7


def _uuid7_str() -> str:
    """Default factory returning a uuidv7 as `str` for aiosqlite compat."""
    return str(uuid7())


class IntroAudioClip(Base):
    """Pre-rendered persona intro clip (ISSUE-017)."""

    __tablename__ = "intro_audio_clips"
    __table_args__ = (
        UniqueConstraint(
            "category",
            "birth_time_variant",
            "character_key",
            name="intro_clips_logical_uq",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        String(36),
        primary_key=True,
        default=_uuid7_str,
    )
    # love | work | money | tarot (matches reading.category).
    category: Mapped[str] = mapped_column(String, nullable=False)
    # known | unknown (matches the saju "birth-time-unknown" flow).
    birth_time_variant: Mapped[str] = mapped_column(String, nullable=False)
    # nuna | dosa.
    character_key: Mapped[str] = mapped_column(String, nullable=False)
    r2_url: Mapped[str] = mapped_column(String, nullable=False)
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    def __repr__(self) -> str:  # pragma: no cover - debug aid
        return (
            f"<IntroAudioClip cat={self.category} "
            f"variant={self.birth_time_variant} char={self.character_key}>"
        )
