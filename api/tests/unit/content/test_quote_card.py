"""ISSUE-056 — quote line extraction via Haiku 4.5.

Tests Acceptance Criteria:

1. Valid reading text → quote ≤ 40 Korean chars.
2. LLM returns > 40 chars → truncate with ``…`` suffix OR fallback.
3. LLM fails → category-appropriate fallback.
4. Quote passes deny-list filter (deny-list integration).

The adapter is fully mocked here — no anthropic SDK reaches over the
wire. The concrete production adapter is exercised by
``test_anthropic_client.py``; we only care that ``extract_quote()``
calls the supplied :class:`LLMAdapter` correctly and post-processes
the result.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest

from voicesaju.content.quote_card import (
    FALLBACK_QUOTES,
    MAX_QUOTE_CHARS,
    extract_quote,
)

# ---------------------------------------------------------------------------
# Helpers — fixture stream adapters
# ---------------------------------------------------------------------------


class _FakeAdapter:
    """Stub LLMAdapter that yields a pre-set token list once per `stream()`.

    Mirrors the runtime_checkable `LLMAdapter` Protocol from
    ``voicesaju.adapters.llm`` — we only need ``stream()``.
    """

    def __init__(self, tokens: list[str]) -> None:
        self._tokens = tokens

    async def stream(self, prompt: str, category: str, seed: str) -> AsyncIterator[str]:
        for tok in self._tokens:
            yield tok


class _RaisingAdapter:
    """LLMAdapter stand-in whose ``stream()`` raises immediately.

    Exercises AC #3 (LLM fails → fallback).
    """

    def __init__(self, exc: Exception) -> None:
        self._exc = exc

    async def stream(self, prompt: str, category: str, seed: str) -> AsyncIterator[str]:
        # The `async def` + `yield` combo is required so this is an async
        # iterator function; the `if False: yield` keeps the body
        # syntactically valid as an async generator without ever
        # yielding before we raise.
        if False:  # pragma: no cover - structural noop
            yield ""
        raise self._exc


# ---------------------------------------------------------------------------
# AC #1 — valid reading text → quote ≤ 40 chars
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_valid_quote_is_returned_within_char_limit() -> None:
    """Adapter returns a short quote → passed through verbatim.

    We pick a quote whose char length is well under the 40 char cap so
    no truncation/fallback path can interfere with the assertion.
    """
    adapter = _FakeAdapter(['"운명은 네가 만든다"'])
    quote = await extract_quote(
        reading_text="아주 긴 리딩 텍스트가 여기 들어옵니다." * 5,
        character_key="nuna",
        category="love",
        adapter=adapter,
    )
    assert quote == "운명은 네가 만든다"
    assert len(quote) <= MAX_QUOTE_CHARS


# ---------------------------------------------------------------------------
# AC #2 — > 40 chars triggers truncation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_overlong_quote_is_truncated_with_ellipsis_suffix() -> None:
    """41+ chars → first 39 chars + `…` (total 40).

    The Korean char count budget is strict per FR-018. We use a 60-char
    string so the truncation path is the only outcome.
    """
    overlong = "가" * 60
    adapter = _FakeAdapter([overlong])
    quote = await extract_quote(
        reading_text="...",
        character_key="nuna",
        category="love",
        adapter=adapter,
    )
    assert len(quote) == MAX_QUOTE_CHARS
    assert quote.endswith("…")
    assert quote == ("가" * 39) + "…"


@pytest.mark.asyncio
async def test_quote_at_exact_limit_is_unchanged() -> None:
    """Exactly 40 chars — boundary case, no `…` appended."""
    exact = "나" * MAX_QUOTE_CHARS
    adapter = _FakeAdapter([exact])
    quote = await extract_quote(
        reading_text="...",
        character_key="dosa",
        category="work",
        adapter=adapter,
    )
    assert quote == exact
    assert len(quote) == MAX_QUOTE_CHARS


# ---------------------------------------------------------------------------
# AC #3 — fallback per category × character
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize("category", ["love", "work", "money", "tarot"])
@pytest.mark.parametrize("character_key", ["nuna", "dosa"])
async def test_fallback_used_when_adapter_raises(
    category: str, character_key: str
) -> None:
    """Adapter explodes → returns a fallback for the right category.

    The fallback table is per-category (3 each) and persona-tagged. We
    don't pin the exact string (so editorial swaps don't break tests)
    but we do require the result to be:

    - non-empty,
    - ≤ 40 chars,
    - drawn from ``FALLBACK_QUOTES[category]``.
    """
    adapter = _RaisingAdapter(RuntimeError("simulated upstream failure"))
    quote = await extract_quote(
        reading_text="...",
        character_key=character_key,
        category=category,
        adapter=adapter,
    )
    assert quote, "fallback must return a non-empty string"
    assert len(quote) <= MAX_QUOTE_CHARS
    assert quote in FALLBACK_QUOTES[category]


@pytest.mark.asyncio
async def test_unknown_category_falls_back_to_love() -> None:
    """Defensive default: unknown category → `love` fallback bucket.

    `love` is picked as the conservative default because it has the
    broadest persona overlap (won't surface "직장" or "타로" copy on a
    misrouted call).
    """
    adapter = _RaisingAdapter(RuntimeError("simulated"))
    quote = await extract_quote(
        reading_text="...",
        character_key="nuna",
        category="unknown",
        adapter=adapter,
    )
    assert quote in FALLBACK_QUOTES["love"]


# ---------------------------------------------------------------------------
# AC #4 — deny-list filter integration
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_denylist_hit_triggers_fallback() -> None:
    """LLM returns a profanity-laden quote → fallback is used.

    We avoid replaying the raw deny-list term by relying on
    ``denylist.has_denylist_hit`` semantics: any quote with a hit fails
    the gate. The substitute path would mangle the quote (it inserts a
    long phrase) so we deliberately reject + fall back instead.
    """
    # "씨발" is a known deny-list term (profanity).
    adapter = _FakeAdapter(["씨발 운명이 망한다"])
    quote = await extract_quote(
        reading_text="...",
        character_key="nuna",
        category="love",
        adapter=adapter,
    )
    assert quote in FALLBACK_QUOTES["love"]


# ---------------------------------------------------------------------------
# Adapter integration — token concatenation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_multi_token_stream_is_concatenated() -> None:
    """Adapter yields tokens in pieces → joined into a single quote string.

    Mirrors the real Anthropic SSE behavior where each yield is a
    partial fragment. The extractor strips wrapping JSON-mode quotes
    and whitespace, so the joined string here is the user-visible quote.
    """
    adapter = _FakeAdapter(['"내일은 ', "더 ", '나은 날이다"'])
    quote = await extract_quote(
        reading_text="...",
        character_key="nuna",
        category="work",
        adapter=adapter,
    )
    assert quote == "내일은 더 나은 날이다"


@pytest.mark.asyncio
async def test_empty_stream_falls_back() -> None:
    """Adapter yields nothing → fallback (defensive)."""
    adapter = _FakeAdapter([])
    quote = await extract_quote(
        reading_text="...",
        character_key="nuna",
        category="money",
        adapter=adapter,
    )
    assert quote in FALLBACK_QUOTES["money"]


# ---------------------------------------------------------------------------
# Fallback table shape
# ---------------------------------------------------------------------------


def test_fallback_table_shape() -> None:
    """3 fallbacks per category, 4 categories → 12 entries.

    Also asserts every entry fits the 40-char budget (otherwise the
    truncate-on-output safety net would mangle them).
    """
    assert set(FALLBACK_QUOTES.keys()) == {"love", "work", "money", "tarot"}
    for cat, quotes in FALLBACK_QUOTES.items():
        assert len(quotes) == 3, f"{cat} needs 3 fallbacks, has {len(quotes)}"
        for q in quotes:
            assert q, f"empty fallback in {cat}"
            assert (
                len(q) <= MAX_QUOTE_CHARS
            ), f"fallback {q!r} exceeds {MAX_QUOTE_CHARS} chars"
