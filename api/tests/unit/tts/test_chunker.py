"""Unit tests for the Korean-aware sentence chunker (ISSUE-037).

Covers:
- Korean ``.?!`` terminators.
- ``..`` and Unicode ``…`` (U+2026) terminators.
- ≤ 120 char cap with whitespace-respecting force-cut.
- Buffer flushing semantics (trailing unterminated fragment).
- Empty input → empty list.
"""

from __future__ import annotations

import pytest

from voicesaju.tts.chunker import (
    DEFAULT_MAX_SENTENCE_CHARS,
    chunk_sentences,
)


def test_empty_input_returns_empty_list() -> None:
    """No text → no chunks. Guards against ``""`` slipping into TTS."""
    assert chunk_sentences("") == []


def test_single_terminator_splits_sentence() -> None:
    """Single ``.`` closes a sentence; the trailing one is preserved."""
    out = chunk_sentences("안녕하세요. 반갑습니다.")
    assert out == ["안녕하세요.", "반갑습니다."]


def test_question_mark_terminates_sentence() -> None:
    """Korean question mark closes a sentence."""
    out = chunk_sentences("어디 가세요? 같이 갈게요.")
    assert out == ["어디 가세요?", "같이 갈게요."]


def test_exclamation_mark_terminates_sentence() -> None:
    """Korean exclamation closes a sentence."""
    out = chunk_sentences("정말요! 대박이네요.")
    assert out == ["정말요!", "대박이네요."]


def test_double_dot_treated_as_single_boundary() -> None:
    """``..`` MUST NOT produce a sentence whose body is just ``.``."""
    out = chunk_sentences("음.. 그래요.")
    assert out == ["음..", "그래요."]


def test_triple_dot_treated_as_single_boundary() -> None:
    """``...`` MUST collapse to a single terminator boundary."""
    out = chunk_sentences("글쎄요... 잘 모르겠어요.")
    assert out == ["글쎄요...", "잘 모르겠어요."]


def test_unicode_ellipsis_terminates_sentence() -> None:
    """Literary ``…`` (U+2026) MUST be recognised as a terminator."""
    out = chunk_sentences("음… 그렇네요.")
    assert out == ["음…", "그렇네요."]


def test_mixed_terminator_run_collapses() -> None:
    """Mixed runs like ``?!`` MUST collapse into one boundary."""
    out = chunk_sentences("진짜?! 말도 안 돼.")
    assert out == ["진짜?!", "말도 안 돼."]


def test_long_unterminated_run_force_split_on_whitespace() -> None:
    """Runs > ``max_chars`` MUST force-split, preferring whitespace."""
    # 150 chars, no terminator, plenty of spaces. Cap=120.
    text = ("매우 " * 75).strip()  # "매우 매우 매우 ..." → ~225 chars
    out = chunk_sentences(text, max_chars=120)
    assert len(out) >= 2
    # No emitted chunk should exceed the cap by more than one word.
    assert all(len(s) <= 120 for s in out)
    # Joining preserves the source content (modulo single-space collapse).
    joined = " ".join(out).replace("  ", " ")
    assert joined.strip() == text.strip()


def test_long_unterminated_no_whitespace_force_cut_at_cap() -> None:
    """Whitespace-less runs MUST still be force-cut at ``max_chars``."""
    text = "가" * 200  # single Korean syllable repeated.
    out = chunk_sentences(text, max_chars=50)
    assert all(len(s) <= 50 for s in out)
    assert "".join(out) == text


def test_default_max_chars_constant_is_120() -> None:
    """Architecture §8.2 budgets sentence chunks at ≤ 120 chars."""
    assert DEFAULT_MAX_SENTENCE_CHARS == 120


def test_trailing_unterminated_returned_as_final_chunk() -> None:
    """A trailing fragment without a terminator MUST be emitted."""
    out = chunk_sentences("첫 문장이에요. 두 번째 문장은 아직 끝나지")
    assert out == ["첫 문장이에요.", "두 번째 문장은 아직 끝나지"]


@pytest.mark.parametrize(
    "text",
    [
        "  ",
        "\n",
        "  \n  \t  ",
    ],
)
def test_whitespace_only_inputs_yield_no_chunks(text: str) -> None:
    """Whitespace-only input MUST NOT produce empty chunks for TTS."""
    assert chunk_sentences(text) == []


def test_leading_space_after_terminator_is_stripped() -> None:
    """Sentences MUST NOT carry leading whitespace into Supertone."""
    out = chunk_sentences("끝.   다시 시작.")
    assert out == ["끝.", "다시 시작."]


def test_ascii_letters_and_korean_mix() -> None:
    """Mixed ASCII + Korean copy MUST split on terminators correctly."""
    out = chunk_sentences("Hello 안녕. World 세상!")
    assert out == ["Hello 안녕.", "World 세상!"]
