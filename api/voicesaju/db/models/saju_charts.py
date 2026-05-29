"""`SajuChart` ORM model.

Schema source of truth: `docs/data_model.md` §4.6 and §5.4.

A `SajuChart` is the computed 4-pillar 명식 row. It is immutable per
generation — when a user corrects their profile (FR-029) a new chart
is computed and inserted, leaving the previous chart in place so old
`readings` keep referencing the same data.

`chart_hash` is a SHA-256 hex digest (64 chars) computed inside the
encryption boundary so the database never sees the birth plaintext used
to derive it. The unique constraint on `chart_hash` enables cache reuse
across users with identical inputs.

Postgres-only constraints (CHECK on `pillars->'hour'` ↔ `time_known`,
partial indexes) are emitted by the migration via raw SQL so SQLite
unit tests can still load the schema.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    String,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from voicesaju.db.base import Base
from voicesaju.db.models.users import uuid7

_JSONColumn = JSON().with_variant(JSONB(), "postgresql")


class SajuChart(Base):
    """Computed 명식 row (data_model §4.6)."""

    __tablename__ = "saju_charts"

    id: Mapped[uuid.UUID] = mapped_column(
        String(36),
        primary_key=True,
        default=uuid7,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    chart_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        unique=True,
    )
    engine_version: Mapped[str] = mapped_column(String, nullable=False)
    pillars: Mapped[dict[str, Any]] = mapped_column(_JSONColumn, nullable=False)
    time_known: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    def __repr__(self) -> str:  # pragma: no cover - debug aid
        return f"<SajuChart id={self.id} hash={self.chart_hash[:8]}...>"
