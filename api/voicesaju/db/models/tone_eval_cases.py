"""`ToneEvalCase` ORM model.

Schema source of truth: ISSUE-018 (FR-032, NFR-010). One row per
labelled tone-evaluation case — used by the offline eval pipeline to
score new prompt versions before they are activated.

The schema intentionally keeps ``case_kind``, ``expected_label``, and
``category_tag`` as ``String`` (not enums) so editorial swaps don't
require migrations. The valid label set (``ok | spicy_ok |
violation_mild | violation_severe``) matches ``tone_eval_label_enum``
in ``docs/data_model.md``; the runtime classifier enforces the
allowed-values invariant at write time.
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


class ToneEvalCase(Base):
    """Labelled tone-evaluation case (ISSUE-018)."""

    __tablename__ = "tone_eval_cases"

    id: Mapped[uuid.UUID] = mapped_column(
        String(36),
        primary_key=True,
        default=_uuid7_str,
    )
    case_kind: Mapped[str] = mapped_column(String, nullable=False)
    input_text: Mapped[str] = mapped_column(Text, nullable=False)
    # ok | spicy_ok | violation_mild | violation_severe — matches
    # tone_eval_label_enum in docs/data_model.md.
    expected_label: Mapped[str] = mapped_column(String, nullable=False)
    # love | work | money | tarot | general.
    category_tag: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    def __repr__(self) -> str:  # pragma: no cover - debug aid
        return (
            f"<ToneEvalCase id={self.id} kind={self.case_kind} "
            f"label={self.expected_label!r}>"
        )
