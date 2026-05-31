"""`AuditEvent` ORM model (ISSUE-088).

Schema source of truth: alembic 0017_audit_events.

Append-only audit log for sensitive lifecycle events. The first event
type — ``'hard_delete'`` — covers the GDPR/PIPA right-to-erasure
trail (NFR-005). Future event types will land alongside their own
work items (login-anomaly, billing-event, ops-override etc.).

Constraints worth noting:

- **No foreign keys** — the referenced row is, by design, deleted by
  the time this row is read for audit. Storing ``entity_id`` as a
  plain string keeps the record stable across cascades.
- **Append-only** — there is no UPDATE/DELETE path on this table.
  The application never edits rows post-insert; the alembic migration
  is the only structural touch.
- **JSON payload** — ``JSON`` round-trips as TEXT on SQLite (unit
  tests) and jsonb on Postgres (production), so the same model file
  works against both dialects without dialect-specific imports.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from voicesaju.db.base import Base
from voicesaju.db.models.users import uuid7


def _uuid7_str() -> str:
    """Default factory: uuidv7 as ``str`` so aiosqlite can bind it."""
    return str(uuid7())


class AuditEvent(Base):
    """Append-only audit log row (data_model — future §4.18 / NFR-005)."""

    __tablename__ = "audit_events"

    id: Mapped[uuid.UUID] = mapped_column(
        String(36),
        primary_key=True,
        default=_uuid7_str,
    )
    entity_type: Mapped[str] = mapped_column(String, nullable=False)
    entity_id: Mapped[str] = mapped_column(String(36), nullable=False)
    event_type: Mapped[str] = mapped_column(String, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    # ``Any`` because callers stash arbitrary JSON-serializable context
    # (R2 keys removed, dependent row counts, etc.). Schema discipline
    # is enforced at the write-site, not the model layer.
    payload: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    def __repr__(self) -> str:  # pragma: no cover - debug aid
        return (
            f"<AuditEvent id={self.id} entity_type={self.entity_type!r} "
            f"event_type={self.event_type!r}>"
        )
