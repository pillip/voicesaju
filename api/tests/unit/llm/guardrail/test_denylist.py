"""Unit tests for the deny-list guardrail (ISSUE-020).

Covers all four scope-in categories — profanity, hate, sexual,
discrimination — plus the borderline ``매운맛 ≠ 욕설`` cases that should
NOT trip the filter, plus block-vs-substitute density behaviour, plus
the character-specific substitute phrase selection.

The Aho-Corasick automaton is built at import time and re-used across
tests; no per-test setup needed.
"""

from __future__ import annotations

import pytest

from voicesaju.llm.guardrail.denylist import (
    FilterResult,
    filter_chunk,
    has_denylist_hit,
    sanitize_evidence,
)

# ---------------------------------------------------------------------------
# pass / clean cases
# ---------------------------------------------------------------------------


def test_empty_string_returns_pass() -> None:
    result = filter_chunk("")
    assert result.action == "pass"
    assert result.text == ""
    assert result.hits == ()


def test_clean_korean_text_returns_pass() -> None:
    text = "오늘은 새로운 도전이 잘 풀릴 흐름이에요."
    result = filter_chunk(text)
    assert result.action == "pass"
    assert result.text == text
    assert result.hits == ()


def test_borderline_spicy_passes() -> None:
    """``매운맛`` is figurative spice (spicy take), not profanity."""
    text = "이번 연애는 매운맛이에요. 그래도 끝까지 본인 페이스를 지키세요."
    result = filter_chunk(text)
    assert result.action == "pass"


# ---------------------------------------------------------------------------
# profanity (욕설)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        "그 사람은 진짜 개새끼니까 빨리 차버려요.",
        "돈 못 버는 사람은 병신이에요.",
        "이 좆같은 운세는 그냥 무시하세요.",
        "카드가 말하길 그 새끼는 쓰레기래요.",
        "이 등신아, 그 사람이랑 헤어져요.",
        "꺼져버려, 이런 미친 운세는 처음 봐요.",
        "지랄 같은 직장 운이네요. 다 때려치우세요.",
        "그 미친놈은 그냥 잘라버려요.",
    ],
)
def test_profanity_is_blocked_or_substituted(text: str) -> None:
    result = filter_chunk(text)
    assert result.action in {
        "substitute",
        "block",
    }, f"unblocked profanity: {text!r} -> {result.action!r}"
    assert "profanity" in result.categories


# ---------------------------------------------------------------------------
# hate / discrimination
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        "여자는 원래 다 멍청하니까 적당히 다뤄요.",
        "남자는 다 똑같이 짐승이에요.",
        "장애인은 직장에서 일 못해요. 같이 일하지 마세요.",
        "동성애자랑은 가까이 지내지 마세요.",
        "그 지역 사람들은 다 사기꾼이니까 거래하지 마세요.",
        "노인들은 어차피 이해 못 해요. 무시하세요.",
        "외국인 동료는 믿을 수 없어요. 거리를 두세요.",
    ],
)
def test_hate_or_discrimination_is_caught(text: str) -> None:
    result = filter_chunk(text)
    assert result.action in {"substitute", "block"}
    # Either "hate" or "profanity" (e.g. "멍청") is acceptable —
    # the AC is that the chunk is not passed unchanged.


# ---------------------------------------------------------------------------
# sexual
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        "오늘 밤은 격렬한 섹스 운이 들어와 있어요.",
        "그 사람과 야한 잠자리를 가질 운이 보여요.",
        "타로 카드가 음란한 관계를 권하고 있어요.",
        "이번 만남에서 야한 행위를 즐기게 될 거예요.",
        "성행위에 대한 운이 강하게 들어와 있어요.",
    ],
)
def test_sexual_content_is_caught(text: str) -> None:
    result = filter_chunk(text)
    assert result.action in {"substitute", "block"}
    assert "sexual" in result.categories


# ---------------------------------------------------------------------------
# substitute behaviour
# ---------------------------------------------------------------------------


def test_substitute_replaces_term_with_safe_phrase() -> None:
    result = filter_chunk("그 사람은 진짜 개새끼니까 빨리 차버려요.")
    assert result.action == "substitute"
    # Default safe phrase appears; the raw profanity does not.
    assert "개새끼" not in result.text
    assert "조심해야 할 부분이" in result.text


def test_character_specific_safe_substitute_for_nuna() -> None:
    result = filter_chunk("그 사람은 진짜 개새끼니까 빨리 차버려요.", character="nuna")
    assert result.action == "substitute"
    assert "조심해야 할 부분이" in result.text


def test_character_specific_safe_substitute_for_dosa() -> None:
    result = filter_chunk("그 사람은 진짜 개새끼니까 빨리 차버려요.", character="dosa")
    assert result.action == "substitute"
    assert "주의가 필요한 흐름이" in result.text


def test_unknown_character_falls_back_to_default() -> None:
    result = filter_chunk("이 좆같은 운세는 그냥 무시하세요.", character="unknown")
    assert result.action == "substitute"
    assert "조심해야 할 부분이" in result.text


def test_adjacent_hits_collapse_into_single_substitute() -> None:
    """Two profanity terms next to each other should not render two
    safe phrases in a row.
    """
    text = "씨발 개새끼"
    result = filter_chunk(text)
    assert result.action in {"substitute", "block"}
    if result.action == "substitute":
        # Default substitute should appear at most once.
        assert result.text.count("조심해야 할 부분이") <= 1


# ---------------------------------------------------------------------------
# hits / categories metadata
# ---------------------------------------------------------------------------


def test_hits_metadata_lists_matched_terms() -> None:
    result = filter_chunk("씨발 그 인간한테 돈 빌려주지 마세요.")
    assert result.action in {"substitute", "block"}
    assert "씨발" in result.hits


def test_categories_metadata_lists_unique_categories() -> None:
    result = filter_chunk("개새끼 같은 동성애자랑은 거래하지 마세요.")
    assert result.action in {"substitute", "block"}
    assert "profanity" in result.categories
    assert "hate" in result.categories


# ---------------------------------------------------------------------------
# evidence sanitization
# ---------------------------------------------------------------------------


def test_sanitize_evidence_masks_profanity() -> None:
    sanitized = sanitize_evidence("씨발 그 인간한테 돈 빌려주지 마세요.")
    assert "씨발" not in sanitized
    # First + last char preserved; middle masked with ●.
    assert "●" in sanitized


def test_sanitize_evidence_preserves_clean_text() -> None:
    text = "오늘은 새로운 도전이 잘 풀릴 흐름이에요."
    assert sanitize_evidence(text) == text


def test_sanitize_evidence_masks_two_char_term() -> None:
    """Two-char deny-list terms (e.g. 좆같) should mask the trailing
    character.
    """
    sanitized = sanitize_evidence("좆 같은 흐름")
    assert "좆" not in sanitized or "●" in sanitized


# ---------------------------------------------------------------------------
# quick-hit boolean
# ---------------------------------------------------------------------------


def test_has_denylist_hit_returns_true_on_match() -> None:
    assert has_denylist_hit("씨발 그 인간한테") is True


def test_has_denylist_hit_returns_false_on_clean() -> None:
    assert has_denylist_hit("오늘은 새로운 도전이") is False


def test_has_denylist_hit_handles_empty() -> None:
    assert has_denylist_hit("") is False


# ---------------------------------------------------------------------------
# FilterResult dataclass invariants
# ---------------------------------------------------------------------------


def test_filter_result_is_frozen() -> None:
    result = filter_chunk("clean")
    with pytest.raises(AttributeError):
        result.action = "block"  # type: ignore[misc]


def test_filter_result_default_tuples_are_empty() -> None:
    result = FilterResult(action="pass", text="clean")
    assert result.hits == ()
    assert result.categories == ()
