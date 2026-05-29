"""``ToneViolationEvent`` insert helper used by the deny-list filter
(ISSUE-020).

Kept separate from :mod:`voicesaju.llm.guardrail.denylist` so the
filter's hot path stays pure (no DB import) and can be exercised in
isolation by unit tests.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from voicesaju.db.models.tone_violation_events import ToneViolationEvent
from voicesaju.db.models.users import uuid7
from voicesaju.llm.guardrail.denylist import FilterResult, sanitize_evidence


@dataclass(frozen=True)
class ViolationParent:
    """Identifier for the parent row a violation is attributed to.

    ``ToneViolationEvent`` requires at least one of ``reading_id`` /
    ``tarot_id`` (per the ``tone_violation_events_parent_chk`` CHECK).
    """

    reading_id: str | None = None
    tarot_id: str | None = None

    def __post_init__(self) -> None:
        if not (self.reading_id or self.tarot_id):
            raise ValueError(
                "ViolationParent requires at least one of "
                "reading_id / tarot_id (tone_violation_events_parent_chk)"
            )


async def record_violation(
    session: AsyncSession,
    *,
    result: FilterResult,
    severity: str,
    parent: ViolationParent,
    evidence_text: str,
) -> ToneViolationEvent:
    """Persist a ``tone_violation_events`` row for a deny-list hit.

    Parameters
    ----------
    session
        Active async session — caller controls the transaction
        boundary; this helper only ``add()`` + ``flush()``.
    result
        The :class:`FilterResult` that the deny-list scan produced.
        Used to attribute the layer + carry the categories list.
    severity
        Either ``"mild"`` or ``"severe"`` (matches
        ``tone_severity_enum`` in ``docs/data_model.md``).
    parent
        Identifier for the originating row. At least one of
        ``reading_id`` / ``tarot_id`` MUST be set or the CHECK
        constraint will fail at flush time.
    evidence_text
        Raw text from the scan. This helper masks deny-list terms via
        :func:`sanitize_evidence` BEFORE the row is persisted so the
        audit log never stores the verbatim profanity.
    """
    if result.action == "pass":
        raise ValueError(
            "record_violation called for a passing FilterResult; "
            "only substitute/block results should be persisted"
        )
    if severity not in {"mild", "severe"}:
        raise ValueError(f"invalid severity: {severity!r}")

    event = ToneViolationEvent(
        id=str(uuid7()),
        reading_id=parent.reading_id,
        tarot_id=parent.tarot_id,
        severity=severity,
        layer="filter",
        evidence_text=sanitize_evidence(evidence_text),
    )
    session.add(event)
    await session.flush()
    return event


__all__ = [
    "ViolationParent",
    "record_violation",
]
