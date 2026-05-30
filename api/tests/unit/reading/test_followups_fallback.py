"""Unit tests for FR-009 fallback question contract (ISSUE-041).

When the LLM adapter raises during the follow-up suggestion call, the
service must return the hardcoded category-specific fallback set with
no propagated exception.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest

from voicesaju.readings.services.followup_service import (
    FOLLOWUP_SUGGEST_COUNT,
    _fallback_questions,
    _parse_questions_payload,
    suggest_followups,
)


class _RaisingLLM:
    """LLMAdapter test double whose ``stream`` raises on first iteration."""

    def __init__(self, exc: Exception) -> None:
        self._exc = exc

    async def stream(self, prompt: str, category: str, seed: str) -> AsyncIterator[str]:
        raise self._exc
        yield ""  # pragma: no cover — make this a generator function.


class _ShortListLLM:
    """LLMAdapter test double that emits a 1-element JSON payload.

    Mirrors the "LLM responded but with fewer questions than expected"
    failure mode — service must still return the 3-item fallback.
    """

    async def stream(self, prompt: str, category: str, seed: str) -> AsyncIterator[str]:
        yield '["one and done"]'


class _GoodLLM:
    """LLMAdapter test double that emits a well-formed 3-question JSON."""

    QUESTIONS = ["llm-q1", "llm-q2", "llm-q3"]

    async def stream(self, prompt: str, category: str, seed: str) -> AsyncIterator[str]:
        import json as _json

        yield _json.dumps(self.QUESTIONS)


# ---------------------------------------------------------------------------
# Fallback selection
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("category", ["love", "work", "money"])
def test_fallback_questions_returns_three_per_category(category: str) -> None:
    """Each supported category ships exactly 3 fallback questions."""
    fallback = _fallback_questions(category)
    assert len(fallback) == FOLLOWUP_SUGGEST_COUNT
    for q in fallback:
        assert isinstance(q, str)
        assert q.strip()


def test_fallback_unknown_category_returns_love_set() -> None:
    """Unknown category falls back to ``love``'s bank (documented choice)."""
    assert _fallback_questions("tarot") == _fallback_questions("love")


# ---------------------------------------------------------------------------
# Parser is tolerant of common LLM drift
# ---------------------------------------------------------------------------


def test_parse_questions_accepts_bare_array() -> None:
    parsed = _parse_questions_payload('["a", "b", "c"]')
    assert parsed == ["a", "b", "c"]


def test_parse_questions_accepts_wrapped_envelope() -> None:
    parsed = _parse_questions_payload('{"questions": ["a", "b", "c"]}')
    assert parsed == ["a", "b", "c"]


def test_parse_questions_strips_bullets_in_newline_fallback() -> None:
    raw = "- a\n- b\n- c"
    parsed = _parse_questions_payload(raw)
    assert parsed == ["a", "b", "c"]


def test_parse_questions_empty_string_returns_empty_list() -> None:
    assert _parse_questions_payload("") == []


# ---------------------------------------------------------------------------
# suggest_followups end-to-end fallback behaviour
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_suggest_followups_falls_back_on_llm_exception() -> None:
    """AC: LLM raises → 3 hardcoded fallback questions returned."""
    llm = _RaisingLLM(RuntimeError("provider down"))

    questions = await suggest_followups(
        reading_id="reading-1",
        category="work",
        llm=llm,
    )

    assert questions == _fallback_questions("work")


@pytest.mark.asyncio
async def test_suggest_followups_falls_back_on_short_list() -> None:
    """LLM returned <3 questions → service falls back to canonical bank."""
    llm = _ShortListLLM()

    questions = await suggest_followups(
        reading_id="reading-2",
        category="money",
        llm=llm,
    )

    assert questions == _fallback_questions("money")


@pytest.mark.asyncio
async def test_suggest_followups_uses_llm_when_payload_is_well_formed() -> None:
    """Happy path: LLM returns 3 questions → service forwards them verbatim."""
    llm = _GoodLLM()

    questions = await suggest_followups(
        reading_id="reading-3",
        category="love",
        llm=llm,
    )

    assert questions == _GoodLLM.QUESTIONS
