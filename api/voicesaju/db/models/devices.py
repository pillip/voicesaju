"""`Device` ORM model.

Schema source of truth: `docs/data_model.md` §4.4.

Non-member identity used by FR-003 (anonymous trial) and FR-013 (free-token
ledger for non-members). `linked_user_id` is nullable because devices are
created before sign-up and only linked to a `users` row after a successful
auth flow (FR-016 device→user merge).
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from voicesaju.db.base import Base
from voicesaju.db.models.users import uuid7


class Device(Base):
    """Device identity row — one per browser/install."""

    __tablename__ = "devices"

    id: Mapped[uuid.UUID] = mapped_column(
        String(36),
        primary_key=True,
        default=uuid7,
    )
    device_id_client: Mapped[str] = mapped_column(
        String,
        nullable=False,
        unique=True,
    )
    linked_user_id: Mapped[uuid.UUID | None] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    user_agent_hash: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
    )

    def __repr__(self) -> str:  # pragma: no cover - debug aid
        return f"<Device id={self.id} client={self.device_id_client}>"
