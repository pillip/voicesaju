"""`CharacterVoice` ORM model.

Schema source of truth: ISSUE-017 (FR-020). One row per persona —
keyed by ``character_key`` so the runtime can look up the active TTS
voice id with a single indexed query.

The seed migration inserts the two M1 personas ("nuna" — cynical
mid-30s Korean female — and "dosa" — elderly mystical Korean male) with
placeholder ``tts_voice_id`` values. The real voice ids are filled in
during persona-tuning (out of scope for the schema PR) and the rest of
the application reads them lazily, so swapping a value is a pure
content update.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from voicesaju.db.base import Base
from voicesaju.db.models.users import uuid7


def _uuid7_str() -> str:
    """Default factory returning a uuidv7 as `str` for aiosqlite compat."""
    return str(uuid7())


class CharacterVoice(Base):
    """Persona voice metadata (ISSUE-017)."""

    __tablename__ = "character_voices"

    id: Mapped[uuid.UUID] = mapped_column(
        String(36),
        primary_key=True,
        default=_uuid7_str,
    )
    # nuna | dosa — the natural key.
    character_key: Mapped[str] = mapped_column(
        String,
        nullable=False,
        unique=True,
    )
    name_kr: Mapped[str] = mapped_column(String, nullable=False)
    tts_voice_id: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    def __repr__(self) -> str:  # pragma: no cover - debug aid
        return f"<CharacterVoice key={self.character_key} name={self.name_kr!r}>"
