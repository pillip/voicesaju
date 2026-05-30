"""`Profile` ORM model.

Schema source of truth: `docs/data_model.md` §4.5 and §5.3.

The `birth_dt` value is **never** stored in plaintext: the column holds a
JSONB envelope (`birth_dt_enc`) populated through `security.envelope`.
Python callers can interact with plaintext via the `birth_dt` property,
which transparently encrypts on write and decrypts on read using
`encrypt_field` / `decrypt_field` from ISSUE-009.

Postgres-only constraints (CHECK on `name_optional` length, partial unique
index on `(user_id)`) are emitted by the migration via raw SQL so the
ORM stays portable to SQLite-backed unit tests.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from voicesaju.db.base import Base
from voicesaju.db.models.users import _uuid7_str
from voicesaju.security import envelope

# Use the dialect-flexible `JSON().with_variant(JSONB(), "postgresql")`
# pattern so SQLite tests can persist the envelope as a JSON column while
# Postgres uses native JSONB (data_model §4.5).
_JSONColumn = JSON().with_variant(JSONB(), "postgresql")


class Profile(Base):
    """User-supplied saju input. Birth datetime is envelope-encrypted.

    Mirrors `docs/data_model.md` §4.5. The plaintext birth datetime is
    exposed through the `birth_dt` Python property only — at rest, only
    the JSONB envelope is stored.
    """

    __tablename__ = "profiles"
    __table_args__ = (
        CheckConstraint(
            "correction_count >= 0 AND correction_count <= 2",
            name="profiles_correction_count_chk",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        String(36),
        primary_key=True,
        default=_uuid7_str,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    birth_dt_enc: Mapped[dict[str, Any]] = mapped_column(
        _JSONColumn,
        nullable=False,
    )
    birth_is_lunar: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )
    birth_time_known: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
    )
    name_optional: Mapped[str | None] = mapped_column(String(10), nullable=True)
    correction_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
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
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # --- envelope accessor ------------------------------------------------
    @property
    def birth_dt(self) -> str | None:
        """Decrypt and return the plaintext birth datetime.

        Returns `None` if `birth_dt_enc` is not set (typically only between
        instantiation and the first assignment). The decrypt path is
        AAD-bound to `(user_id, "birth_dt")` so swapping envelopes between
        rows is detected as an `AADMismatchError`.
        """
        if not self.birth_dt_enc:
            return None
        if self.user_id is None:
            raise ValueError("Profile.user_id must be set before reading birth_dt")
        return envelope.decrypt_field(
            self.birth_dt_enc,
            user_id=self.user_id,
            column="birth_dt",
        )

    @birth_dt.setter
    def birth_dt(self, plaintext: str) -> None:
        """Encrypt `plaintext` and store the envelope in `birth_dt_enc`.

        Requires `user_id` to already be set so the AAD can bind the
        ciphertext to its owning row (defeats row-swap attacks per
        data_model §4.25).
        """
        if self.user_id is None:
            raise ValueError("Profile.user_id must be set before writing birth_dt")
        self.birth_dt_enc = envelope.encrypt_field(
            plaintext,
            user_id=self.user_id,
            column="birth_dt",
        )

    def __init__(self, *, birth_dt: str | None = None, **kwargs: Any) -> None:
        """Mirror the SA `__init__` while supporting the `birth_dt` shortcut.

        Allows `Profile(user_id=u, birth_dt="2000-...")` so callers don't
        have to drive the property setter manually. The plaintext keyword
        is consumed before the standard `Base.__init__` runs so SA does
        not try to map it onto a (non-existent) column.
        """
        super().__init__(**kwargs)
        if birth_dt is not None:
            self.birth_dt = birth_dt

    def __repr__(self) -> str:  # pragma: no cover - debug aid
        return f"<Profile id={self.id} user_id={self.user_id}>"
