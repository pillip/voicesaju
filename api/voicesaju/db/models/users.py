"""`User` ORM model.

Schema source of truth: `docs/data_model.md` §4.2.

Constraints/indexes that are inherently Postgres-only — partial unique
indexes on `kakao_sub`/`apple_sub`/`toss_id`, the multi-column CHECK
requiring ≥1 provider — are declared in the Alembic migration via raw
`op.execute`. The ORM model declares only column-level metadata so that
SQLite-backed unit tests can still reflect a sane schema for model wiring.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from voicesaju.db.base import Base

try:  # pragma: no cover - import path guarded by fallback below
    from uuid_utils import uuid7 as _uuid7

    def uuid7() -> uuid.UUID:  # type: ignore[no-redef]
        """Return a uuidv7 as a stdlib `uuid.UUID`."""
        return uuid.UUID(str(_uuid7()))

except ImportError:  # pragma: no cover - exercised without uuid-utils

    def uuid7() -> uuid.UUID:
        """Fallback uuid4 when `uuid-utils` is unavailable."""
        return uuid.uuid4()


def _uuid7_str() -> str:
    """Return a uuidv7 as `str` so aiosqlite can bind it without conversion.

    Matches the convention used across newer models (payments, readings,
    tarot_cards, etc.) — `String(36)` PK columns receive a stringified UUID
    rather than a `uuid.UUID` instance, which the pure-Python aiosqlite
    driver cannot bind.
    """
    return str(uuid7())


class User(Base):
    """Identity root — one row per VoiceSaju account.

    Mirrors `docs/data_model.md` §4.2. Columns are kept SQLite-compatible
    (`String` instead of Postgres-only types) where possible; Postgres-only
    constraints (partial unique indexes, multi-column CHECK) are declared
    inside the migration via raw SQL so the ORM stays portable.
    """

    __tablename__ = "users"
    __table_args__ = (
        # Application-level CHECK so SQLAlchemy emits it on both Postgres
        # and SQLite. The Postgres migration *also* emits the same
        # constraint via raw SQL for clarity and to keep it visible in
        # `\d users` even when the model is not loaded.
        CheckConstraint(
            "kakao_sub IS NOT NULL OR apple_sub IS NOT NULL OR toss_id IS NOT NULL",
            name="users_provider_present_chk",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        String(36),
        primary_key=True,
        default=_uuid7_str,
    )
    kakao_sub: Mapped[str | None] = mapped_column(String, nullable=True)
    apple_sub: Mapped[str | None] = mapped_column(String, nullable=True)
    toss_id: Mapped[str | None] = mapped_column(String, nullable=True)
    email_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    display_locale: Mapped[str] = mapped_column(
        String, nullable=False, default="ko-KR", server_default="ko-KR"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    last_seen_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    def __repr__(self) -> str:  # pragma: no cover - debug aid
        return f"<User id={self.id} created_at={self.created_at}>"
