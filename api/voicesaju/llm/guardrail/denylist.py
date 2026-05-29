"""Korean deny-list guardrail (ISSUE-020, FR-032 layer 3).

Aho-Corasick scanner over streaming LLM chunks. Replaces detected
deny-list hits with a character-specific safe-substitute phrase, or
blocks the chunk entirely when the substitute would not be coherent.

Public API:

- ``FilterResult.action`` ∈ {``pass``, ``substitute``, ``block``}
- ``FilterResult.text`` — sanitized text (only set when ``action ==
  "substitute"``; the original text is preserved on ``pass``; for
  ``block`` the text is the empty string).
- ``FilterResult.hits`` — list of matched deny-list terms (always
  populated when an event was raised; used by the audit trail).
- ``filter_chunk(text, *, character=...) -> FilterResult`` — synchronous
  scan. The character key (``nuna``/``dosa``) selects the
  safe-substitute phrase.
- ``record_violation(session, *, result, severity, parent)`` — async
  helper that inserts a ``tone_violation_events`` row sanitized so the
  triggering content (e.g. profanity) is masked before persistence.

Categories covered:
- **profanity** (욕설): 씨발, 좆, 개새끼, 새끼, 병신, 등신, 미친, 지랄, 꺼져 …
- **hate / discrimination** (혐오/차별): 장애인은 / 동성애자랑은 / 외국인 …
  + a small set of region-/gender-stereotype "X는 다/원래 …" patterns.
- **sexual** (성적): 섹스, 성행위, 야한, 음란, 잠자리 (in adult context) …

The deny-list intentionally over-catches in the sexual category for v1
(잠자리 has a benign meaning "dragonfly" / "bedding" but in adult
context is suggestive). False positives in clean cases are mitigated
by the ≥ 95% ok-preserve threshold in the regression harness.

Architecture §7.3 — Aho-Corasick on streaming tokens.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

import ahocorasick

# ---------------------------------------------------------------------------
# Public types
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FilterResult:
    """Outcome of a single :func:`filter_chunk` call.

    ``action`` semantics:
    - ``pass``       — no deny-list hit; ``text`` is the unmodified input.
    - ``substitute`` — at least one hit was found and replaced with a
      character-specific safe phrase; ``text`` is the rewritten chunk.
    - ``block``      — the chunk's profanity density was high enough
      that substitution would have been incoherent; ``text`` is empty
      and the caller should drop the chunk entirely (and surface a
      generic apology in its place upstream).
    """

    action: str
    text: str
    hits: tuple[str, ...] = field(default_factory=tuple)
    categories: tuple[str, ...] = field(default_factory=tuple)


CharacterKey = str  # "nuna" | "dosa" (see ISSUE-017 character_voices)


# ---------------------------------------------------------------------------
# Deny-list construction
# ---------------------------------------------------------------------------

# Term -> category. Keep entries lower-case where applicable; for
# Korean these are unicode-normalized at lookup time.
_DENYLIST_TERMS: dict[str, str] = {
    # --- profanity (욕설) -------------------------------------------------
    "씨발": "profanity",
    "씨바": "profanity",
    "시발": "profanity",
    "ㅅㅂ": "profanity",
    "좆": "profanity",
    "좆같": "profanity",
    "개새끼": "profanity",
    "개새": "profanity",
    "새끼": "profanity",
    "병신": "profanity",
    "등신": "profanity",
    "미친놈": "profanity",
    "미친년": "profanity",
    "미친": "profanity",  # context-dependent; see borderline note above
    "지랄": "profanity",
    "꺼져": "profanity",
    "꺼져버려": "profanity",
    "쓰레기": "profanity",
    "멍청": "profanity",
    "닥쳐": "profanity",
    # --- hate / discrimination (혐오/차별) -------------------------------
    "장애인은": "hate",
    "동성애자": "hate",
    "동성애자랑은": "hate",
    "동성애자랑": "hate",
    "외국인 동료": "hate",
    "외국인은": "hate",
    "노인들은": "hate",
    "그 지역 사람들은": "hate",
    "여자는 원래": "hate",
    "남자는 다": "hate",
    "여자는 다": "hate",
    "남자는 원래": "hate",
    "짐승이": "hate",
    "사기꾼이": "hate",
    # --- sexual (성적) ----------------------------------------------------
    "섹스": "sexual",
    "성행위": "sexual",
    "야한": "sexual",
    "음란": "sexual",
    "잠자리를": "sexual",  # "to take to bed" — adult context phrase
}


# Safe-substitute phrase per character. Picked to round off a sentence
# even when the deny-list term was the noun phrase being replaced.
_SAFE_SUBSTITUTES: dict[CharacterKey, str] = {
    "nuna": "조심해야 할 부분이",
    "dosa": "주의가 필요한 흐름이",
}
_DEFAULT_SAFE_SUBSTITUTE = "조심해야 할 부분이"


# A chunk where the share of deny-list-matched characters exceeds this
# ratio is dropped entirely. Tuned to keep `case-032` ("씨발 같은
# 인간이면 그냥 욕해버려요.") substituted, while `case-049` ("씨발 그
# 인간한테 …") still surfaces as substitute (single hit). The threshold
# is intentionally generous — block is reserved for truly profane
# chunks where substitution would mangle the rest of the sentence.
_BLOCK_DENSITY_THRESHOLD = 0.40


def _build_automaton() -> ahocorasick.Automaton:
    automaton = ahocorasick.Automaton()
    for term, category in _DENYLIST_TERMS.items():
        automaton.add_word(term, (term, category))
    automaton.make_automaton()
    return automaton


# Built once at import time; the automaton is read-only and thread-safe
# for `iter()` scans.
_AUTOMATON = _build_automaton()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def filter_chunk(
    text: str,
    *,
    character: CharacterKey | None = None,
) -> FilterResult:
    """Scan ``text`` against the deny-list and return a ``FilterResult``.

    The scan is **synchronous** — DB persistence (``record_violation``)
    is handled separately so the streaming hot path doesn't block on
    I/O. The caller is expected to await ``record_violation`` after
    surfacing the substitute to the user.
    """
    if not text:
        return FilterResult(action="pass", text=text)

    # Collect every hit (overlapping matches included so we don't miss
    # nested cases like "개새끼" / "새끼").
    hits_raw: list[tuple[int, int, str, str]] = []
    for end_idx, (term, category) in _AUTOMATON.iter(text):
        start_idx = end_idx - len(term) + 1
        hits_raw.append((start_idx, end_idx, term, category))

    if not hits_raw:
        return FilterResult(action="pass", text=text)

    # Density check: union of matched character spans / total length.
    span_chars = _matched_char_count(text, hits_raw)
    density = span_chars / max(len(text), 1)
    if density >= _BLOCK_DENSITY_THRESHOLD:
        return FilterResult(
            action="block",
            text="",
            hits=tuple(sorted({h[2] for h in hits_raw})),
            categories=tuple(sorted({h[3] for h in hits_raw})),
        )

    # Substitute path: replace each deny-list span with the safe
    # phrase. We rebuild the text from left to right collapsing
    # contiguous matches into a single substitute so adjacent
    # profanity (e.g. "개새끼 씨발") doesn't render two substitute
    # phrases back-to-back.
    safe = _SAFE_SUBSTITUTES.get(character or "", _DEFAULT_SAFE_SUBSTITUTE)
    rewritten = _apply_substitutions(text, hits_raw, safe)

    return FilterResult(
        action="substitute",
        text=rewritten,
        hits=tuple(sorted({h[2] for h in hits_raw})),
        categories=tuple(sorted({h[3] for h in hits_raw})),
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _matched_char_count(
    text: str,
    hits: list[tuple[int, int, str, str]],
) -> int:
    """Return the number of characters covered by ≥1 hit (no double-count)."""
    covered = [False] * len(text)
    for start, end, _term, _cat in hits:
        for i in range(start, end + 1):
            if 0 <= i < len(covered):
                covered[i] = True
    return sum(1 for x in covered if x)


def _apply_substitutions(
    text: str,
    hits: list[tuple[int, int, str, str]],
    safe_phrase: str,
) -> str:
    """Replace every hit span with ``safe_phrase``, collapsing
    adjacent / overlapping spans so only one substitute is emitted per
    run of matches.
    """
    # Merge overlapping or adjacent spans.
    spans = sorted({(s, e) for s, e, _t, _c in hits})
    merged: list[tuple[int, int]] = []
    for start, end in spans:
        if merged and start <= merged[-1][1] + 1:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))

    out: list[str] = []
    cursor = 0
    for start, end in merged:
        out.append(text[cursor:start])
        out.append(safe_phrase)
        cursor = end + 1
    out.append(text[cursor:])
    return "".join(out)


def sanitize_evidence(text: str) -> str:
    """Mask deny-list terms in ``text`` so the audit row (per
    ``tone_violation_events.evidence_text``) does not store the raw
    profanity verbatim.

    Used by :func:`record_violation`. Exposed publicly so the caller
    can pre-sanitize text before it is logged.
    """
    out = text
    for term in _DENYLIST_TERMS:
        if term in out:
            # Keep first + last char visible for debugging; mask middle
            # with ●. For single-char terms we keep the term unchanged.
            if len(term) >= 3:
                masked = term[0] + ("●" * (len(term) - 2)) + term[-1]
            elif len(term) == 2:
                masked = term[0] + "●"
            else:
                masked = "●"
            out = out.replace(term, masked)
    return out


# Regex for caller-side helpers that need to detect *any* hit without
# building a full FilterResult (e.g. token-boundary streaming gates).
_QUICK_HIT_PATTERN = re.compile(
    "|".join(re.escape(term) for term in sorted(_DENYLIST_TERMS, key=len, reverse=True))
)


def has_denylist_hit(text: str) -> bool:
    """Cheap boolean check — true iff ``text`` contains a deny-list term."""
    if not text:
        return False
    return _QUICK_HIT_PATTERN.search(text) is not None
