"""`ReadingAudio` ORM model.

Schema source of truth: `docs/data_model.md` §4.11 and §5.7.

R2 pointer + metadata for the main audio. ``duration_ms`` is constrained
to FR-007's 60-120 sec window so clipped or runaway audio segments are
caught at insert time.
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
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from voicesaju.db.base import Base
from voicesaju.db.models.users import uuid7


def _uuid7_str() -> str:
    return str(uuid7())


class ReadingAudio(Base):
    """1:1 R2 audio metadata row per reading (data_model §4.11)."""

    __tablename__ = "reading_audio"
    __table_args__ = (
        # AC: `duration_ms BETWEEN 60000 AND 120000` (FR-007 window).
        CheckConstraint(
            "duration_ms >= 60000 AND duration_ms <= 120000",
            name="audio_duration_chk",
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
    r2_url: Mapped[str] = mapped_column(String, nullable=False)
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    # ISSUE-038: object-store key (e.g. ``audio/readings/<id>/main.mp3``).
    # Stored alongside ``r2_url`` so we can re-issue presigned URLs from
    # the key without re-parsing the URL host.
    r2_key: Mapped[str | None] = mapped_column(String, nullable=True)
    # ISSUE-038: SHA-256 of the stitched main.mp3 byte content. Lets
    # the replay endpoint serve a stable ``ETag`` and detect bit-rot
    # against the storage layer.
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # ISSUE-038: byte size of the stitched main.mp3. Used by the
    # replay ``Range`` handler to compute the final byte boundary
    # without an extra ``stat`` call against R2.
    file_size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    def __repr__(self) -> str:  # pragma: no cover - debug aid
        return (
            f"<ReadingAudio reading_id={self.reading_id} "
            f"duration_ms={self.duration_ms}>"
        )
