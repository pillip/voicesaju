"""Quote line extraction (ISSUE-056, FR-018).

Calls the LLMAdapter (Haiku 4.5 router target for short-form
extraction) to distil a finished reading down to a single spicy quote
line ≤ 40 Korean chars. Falls back to a curated list when the LLM
fails, returns nonsense (empty or oversized), or trips the deny-list
guardrail from ISSUE-020.

Why this lives in `content/` rather than `llm/`:

- ``llm/`` houses the **provider-agnostic** clients (Anthropic SDK
  wrapper, cost tracker, router) — anything that talks tokens.
- ``content/`` houses **per-feature** prompt orchestration. Quote
  extraction is one prompt for one feature (FR-018); putting it next
  to ``quote_card_service`` (ISSUE-057) keeps the read path / write
  path / OG bake worker (ISSUE-058) in the same package.

PRD-Ref: FR-018.
Architecture-Ref: §7.1 (Haiku for short-form), §7.3 (deny-list
guardrail).
"""

from __future__ import annotations

import logging
import random

from voicesaju.adapters import get_llm_adapter
from voicesaju.adapters.llm import LLMAdapter
from voicesaju.llm.guardrail.denylist import has_denylist_hit

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Hard cap from FR-018 AC #1. The 40-char budget is measured in Python
# `len()` (== Unicode code points) — fine for Korean Hangul which is
# one code point per syllable block.
MAX_QUOTE_CHARS: int = 40

# When the LLM returns something longer than the budget we truncate to
# (MAX - 1) chars and append `…` so the rendered card never overflows.
# 39 + 1 = 40, which preserves the AC #1 invariant.
_ELLIPSIS = "…"

# Wrapping characters the LLM tends to add even when prompted for plain
# text (quotes, brackets, smart quotes). We strip these defensively
# before measuring + serving so the card layout doesn't render dangling
# punctuation.
_STRIP_CHARS = " \t\n\r\"'`"


# ---------------------------------------------------------------------------
# Fallback table (FR-018 AC #4 — "3 fallback quotes per category at launch")
# ---------------------------------------------------------------------------
#
# Tone is intentionally aligned with the 시니컬 누님 persona (mid-30s
# skeptical Korean female); the persona switch to 노인 도사 is handled
# by `quote_card_service.create_for_tarot` selecting `category='tarot'`
# rather than swapping the table per character (the lines below read
# well in both voices).
#
# All entries are ≤ 40 chars; the test
# ``test_fallback_table_shape`` enforces this so editorial swaps
# can't silently break AC #1.
FALLBACK_QUOTES: dict[str, tuple[str, ...]] = {
    "love": (
        "마음 가는 곳에 답이 있다.",
        "흔들릴 때 진심이 보인다.",
        "기다림도 사랑의 일부다.",
    ),
    "work": (
        "버티는 사람이 결국 이긴다.",
        "지금의 노력은 내일의 무기다.",
        "조용히 실력을 쌓아둬라.",
    ),
    "money": (
        "급할수록 천천히 가라.",
        "돈은 너를 따라오는 그림자다.",
        "쓸 때와 모을 때를 구분해라.",
    ),
    "tarot": (
        "오늘의 카드가 길을 비춘다.",
        "운명은 네 손 안에 있다.",
        "신호를 놓치지 마라.",
    ),
}

# Conservative default when the caller passes a category we don't have
# a fallback bucket for. `love` is broadest tonally and won't surface
# 직장/타로-specific copy on a misrouted call.
_DEFAULT_FALLBACK_CATEGORY = "love"


# ---------------------------------------------------------------------------
# Prompt
# ---------------------------------------------------------------------------


_PROMPT_TEMPLATE = (
    "다음은 사주 또는 타로 리딩 내용입니다. "
    "여기서 가장 인상적이고 공유할 만한 한 줄 명언을 한국어로 추출하세요. "
    "조건: \n"
    "- 40자 이내(공백 포함).\n"
    "- 따옴표나 부연 설명 없이 한 줄만 출력.\n"
    "- 욕설/혐오/성적 표현 금지.\n"
    "\n"
    "[캐릭터: {character_key}]\n"
    "[카테고리: {category}]\n"
    "\n"
    "[리딩 내용]\n"
    "{reading_text}\n"
)


def _build_prompt(*, reading_text: str, character_key: str, category: str) -> str:
    return _PROMPT_TEMPLATE.format(
        reading_text=reading_text,
        character_key=character_key,
        category=category,
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def extract_quote(
    reading_text: str,
    character_key: str,
    category: str,
    *,
    adapter: LLMAdapter | None = None,
    rng: random.Random | None = None,
) -> str:
    """Return a spicy ≤ 40 char quote extracted from *reading_text*.

    Args:
        reading_text: The full streamed/finalized reading body. The
            extraction prompt is appended to this so the LLM has the
            full context.
        character_key: ``"nuna"`` or ``"dosa"`` — currently used to
            tag the prompt + (if AC #3 fires) to pick a persona-tinted
            fallback. Future persona-divergent fallbacks can branch
            here without changing the public signature.
        category: One of ``"love"`` / ``"work"`` / ``"money"`` /
            ``"tarot"``. Drives both the prompt tag and the fallback
            bucket.
        adapter: Optional :class:`LLMAdapter` override. Defaults to the
            factory (``get_llm_adapter()``) — Phase-1 routes through
            :class:`MockLLMAdapter`; Phase-2 swaps to
            :class:`ClaudeAdapter` automatically via env.
        rng: Optional ``random.Random`` instance for deterministic
            fallback selection. Useful in tests; production callers
            pass nothing and we use the module-level default.

    Returns:
        A ≤ 40 char Korean quote string. Never empty, never raises —
        any failure path resolves to a fallback so the calling
        pipeline (ISSUE-057) can always insert a row.

    Notes:
        - The deny-list gate is conservative — any hit causes a
          fallback rather than substitute, because the substitute
          phrase (`"조심해야 할 부분이"`) doesn't read naturally as a
          standalone spicy quote. The substitute path is fine for the
          streaming reading body where it can slot into a sentence;
          here we want a clean line.
        - Truncation is `O(1)` Unicode code-point slicing — adequate
          for Korean Hangul where one code point == one rendered
          glyph block in the OG image font.
    """
    rng = rng or _RNG_DEFAULT

    # 1. Try the LLM. Catch broadly because the failure modes from
    #    `ClaudeAdapter.stream()` are diverse (LLMClientError,
    #    LLMTimeoutError, network blips, async cancellation) and the
    #    UX behaviour is identical for all of them: serve a fallback.
    try:
        adapter = adapter or get_llm_adapter()
        prompt = _build_prompt(
            reading_text=reading_text,
            character_key=character_key,
            category=category,
        )
        # `seed` is the prompt itself — the mock adapter uses it to
        # pick a deterministic fixture; the real adapter ignores it
        # (it goes into metadata, not the request body). Hashing keeps
        # the seed compact for log lines.
        seed = f"quote_card:{character_key}:{category}"
        chunks: list[str] = []
        async for token in adapter.stream(prompt, "tarot", seed):
            # Route via "tarot" task category so the real adapter
            # picks the Haiku model (cheap + fast for short-form
            # extraction). Reading category goes in the prompt body.
            chunks.append(token)
        raw = "".join(chunks).strip(_STRIP_CHARS)
    except Exception as exc:  # noqa: BLE001 — covered by AC #3
        logger.warning(
            "quote_card.extract_quote: LLM failed (%s); using fallback "
            "category=%s character=%s",
            exc.__class__.__name__,
            category,
            character_key,
        )
        return _pick_fallback(category, rng=rng)

    # 2. Empty / whitespace-only → fallback. The LLM can return zero
    #    tokens on a malformed completion; treat the same as failure.
    if not raw:
        logger.warning(
            "quote_card.extract_quote: empty completion; using fallback "
            "category=%s character=%s",
            category,
            character_key,
        )
        return _pick_fallback(category, rng=rng)

    # 3. Deny-list gate. We use the cheap `has_denylist_hit` boolean
    #    rather than the full FilterResult because we want to reject
    #    on ANY hit — substitution would corrupt the quote.
    if has_denylist_hit(raw):
        logger.warning(
            "quote_card.extract_quote: deny-list hit; using fallback "
            "category=%s character=%s",
            category,
            character_key,
        )
        return _pick_fallback(category, rng=rng)

    # 4. Length enforcement. ≤ MAX_QUOTE_CHARS → return verbatim;
    #    longer → truncate to (MAX - 1) + ellipsis so the final string
    #    is exactly MAX chars.
    if len(raw) <= MAX_QUOTE_CHARS:
        return raw
    return raw[: MAX_QUOTE_CHARS - 1] + _ELLIPSIS


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------


# Module-level RNG so production callers don't have to thread one
# through. Tests pass their own seeded `random.Random(seed)` for
# determinism when the fallback bucket has > 1 entry.
_RNG_DEFAULT = random.Random()


def _pick_fallback(category: str, *, rng: random.Random) -> str:
    """Return one random quote from the bucket for *category*.

    Unknown categories fall through to ``_DEFAULT_FALLBACK_CATEGORY``
    (`love`) rather than raising so the caller's invariant —
    "extract_quote never throws" — holds.
    """
    bucket = (
        FALLBACK_QUOTES.get(category) or FALLBACK_QUOTES[_DEFAULT_FALLBACK_CATEGORY]
    )
    return rng.choice(bucket)


__all__ = [
    "FALLBACK_QUOTES",
    "MAX_QUOTE_CHARS",
    "extract_quote",
]
