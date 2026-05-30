"""Model routing — Sonnet 4.6 vs Haiku 4.5 per task kind.

Implements Architecture §7.1 routing rules as a pure function. No I/O,
no async. Centralising the routing here means the rest of the LLM
pipeline never sees raw model-ID strings, which keeps the NFR-007 cost
ceiling argument auditable: every call site explicitly declares its
`TaskKind`, and only ``select_model`` decides which model to call.

Architecture §7.1 mapping:

| Task kind                | Model      |
|--------------------------|------------|
| ``SAJU_MAIN``            | Sonnet 4.6 |
| ``FOLLOWUP_SUGGEST``     | Haiku 4.5  |
| ``FOLLOWUP_ANSWER``      | Haiku 4.5  |
| ``TAROT``                | Haiku 4.5  |
| ``QUOTE_EXTRACT``        | Haiku 4.5  |

**No runtime auto-fallback** Haiku → Sonnet — that would defeat the
cost-budget modelling. Failure mode is the FR-033 fallback path (handled
upstream in the reading pipeline).
"""

from __future__ import annotations

from enum import StrEnum
from typing import Final

# ---------------------------------------------------------------------------
# Model IDs
# ---------------------------------------------------------------------------
#
# These IDs follow Anthropic's 2025-late naming. They are the values the
# `anthropic` Python SDK accepts as `model=`. If a future SDK release
# changes the canonical string (e.g. drops the trailing date suffix on
# Haiku), update here only — every call site reads through these
# constants.
#
# Reference values come from the installed ``anthropic`` SDK's published
# model list. See PRD §11 OQ-01 for the (still-open) exact pricing
# discussion — the IDs themselves are stable across pricing changes.

SONNET_4_6: Final[str] = "claude-sonnet-4-6"
HAIKU_4_5: Final[str] = "claude-haiku-4-5-20251001"


class TaskKind(StrEnum):
    """Closed set of LLM call kinds the reading pipeline issues.

    Inheriting from ``StrEnum`` makes the enum JSON-serialisable for
    logging + metrics tagging without a custom encoder.

    Adding a value here is a deliberate decision: every new kind needs a
    routing rule in ``select_model`` and a price tag in ``cost_tracker``
    consumers. The router test pins the exact enum membership so the
    check happens at CI time.
    """

    SAJU_MAIN = "saju_main"
    FOLLOWUP_SUGGEST = "followup_suggest"
    FOLLOWUP_ANSWER = "followup_answer"
    TAROT = "tarot"
    QUOTE_EXTRACT = "quote_extract"


# Static routing table — checked at import time via the unit test that
# pins the enum membership. A dict keyed by ``TaskKind`` (not a chain of
# ``if``s) keeps the routing rule both fast and obvious at a glance.
_MODEL_BY_KIND: Final[dict[TaskKind, str]] = {
    TaskKind.SAJU_MAIN: SONNET_4_6,
    TaskKind.FOLLOWUP_SUGGEST: HAIKU_4_5,
    TaskKind.FOLLOWUP_ANSWER: HAIKU_4_5,
    TaskKind.TAROT: HAIKU_4_5,
    TaskKind.QUOTE_EXTRACT: HAIKU_4_5,
}


def select_model(task_kind: TaskKind) -> str:
    """Return the Anthropic model ID to use for the given ``task_kind``.

    Raises:
        ValueError: if ``task_kind`` is not a known ``TaskKind`` (e.g.,
            a stale string from an out-of-date caller). We fail loudly
            because the alternative — silently defaulting to Sonnet —
            blows the cost ceiling.
    """
    # Coerce strings for backward compatibility with logging/tag inputs,
    # but reject anything we don't recognise.
    if isinstance(task_kind, str) and not isinstance(task_kind, TaskKind):
        try:
            task_kind = TaskKind(task_kind)
        except ValueError as exc:
            raise ValueError(
                f"Unknown task_kind: {task_kind!r}. "
                f"Allowed: {[k.value for k in TaskKind]}"
            ) from exc

    if task_kind not in _MODEL_BY_KIND:
        raise KeyError(
            f"No routing rule for task_kind={task_kind!r}. "
            f"Add it to llm.router._MODEL_BY_KIND."
        )

    return _MODEL_BY_KIND[task_kind]


__all__ = [
    "HAIKU_4_5",
    "SONNET_4_6",
    "TaskKind",
    "select_model",
]
