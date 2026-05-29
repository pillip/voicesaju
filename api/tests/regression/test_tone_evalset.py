"""Tone evalset regression harness (ISSUE-019, FR-032 layer-2).

This test serves a dual purpose:

1. **Fixture shape gate** (always-on): the ``tests/fixtures/tone_evalset.json``
   file MUST contain ≥ 50 well-formed cases. Every case must declare a
   ``case_kind`` ∈ {``ok``, ``spicy_ok``, ``violation``}, an
   ``expected_label`` ∈ {``ok``, ``spicy_ok``, ``violation_mild``,
   ``violation_severe``}, a ``category_tag`` ∈ {``love``, ``work``,
   ``money``, ``tarot``, ``general``}, and non-empty Korean
   ``input_text``. This guarantees future editorial swaps cannot
   silently break the regression contract.

2. **Deny-list correctness gate** (`tone_regression` marker, deferred to
   ISSUE-020): when ``voicesaju.llm.guardrail.denylist`` exists, replay
   every fixture case through ``filter_chunk`` and assert:
   - 100% of ``violation`` cases are blocked or substituted,
   - ≥ 95% of ``ok`` cases pass unmodified,
   - ``spicy_ok`` borderline cases (e.g. "매운맛 ≠ 욕설") pass — they
     test that the deny-list does NOT over-trigger on figurative
     language.

   ISSUE-019 ships the harness with the deny-list import guarded by
   ``pytest.importorskip``. The test parameter expansion still runs in
   ISSUE-019's CI, so any future fixture-shape regression is caught
   immediately. The 100% / 95% deny-list assertions flip green
   automatically once ISSUE-020 lands its ``denylist`` module — no
   harness changes required.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

# Fixture lives next to this test under ``tests/fixtures``.
_FIXTURE_PATH = Path(__file__).resolve().parents[1] / "fixtures" / "tone_evalset.json"

# Allowed enumerations — keep in sync with ``docs/data_model.md`` §4
# and ISSUE-018 model docstrings.
_ALLOWED_CASE_KINDS = {"ok", "spicy_ok", "violation"}
_ALLOWED_EXPECTED_LABELS = {
    "ok",
    "spicy_ok",
    "violation_mild",
    "violation_severe",
}
_ALLOWED_CATEGORIES = {"love", "work", "money", "tarot", "general"}

# Minimum fixture size (FR-032 release gate). Raising this is fine;
# lowering it requires explicit team approval — every case is editorial
# work and reflects an observed failure mode.
_MIN_CASES = 50

# Acceptance thresholds for the deny-list (ISSUE-020).
_VIOLATION_BLOCK_RATE = 1.0  # 100%
_OK_PRESERVE_RATE = 0.95  # ≥ 95%


def _load_fixture() -> list[dict]:
    with _FIXTURE_PATH.open("r", encoding="utf-8") as fh:
        return json.load(fh)


# ---------------------------------------------------------------------------
# 1) Fixture-shape gates — always-on (no marker).
# ---------------------------------------------------------------------------


def test_fixture_file_exists() -> None:
    assert _FIXTURE_PATH.exists(), f"fixture not found: {_FIXTURE_PATH}"


def test_fixture_has_minimum_cases() -> None:
    cases = _load_fixture()
    assert (
        len(cases) >= _MIN_CASES
    ), f"tone_evalset.json must contain >= {_MIN_CASES} cases, got {len(cases)}"


def test_fixture_case_kinds_are_valid() -> None:
    cases = _load_fixture()
    for case in cases:
        assert (
            case["case_kind"] in _ALLOWED_CASE_KINDS
        ), f"case {case['id']!r} has invalid case_kind: {case['case_kind']!r}"


def test_fixture_expected_labels_are_valid() -> None:
    cases = _load_fixture()
    for case in cases:
        assert case["expected_label"] in _ALLOWED_EXPECTED_LABELS, (
            f"case {case['id']!r} has invalid expected_label: "
            f"{case['expected_label']!r}"
        )


def test_fixture_categories_are_valid() -> None:
    cases = _load_fixture()
    for case in cases:
        assert (
            case["category_tag"] in _ALLOWED_CATEGORIES
        ), f"case {case['id']!r} has invalid category_tag: {case['category_tag']!r}"


def test_fixture_input_text_is_non_empty_korean() -> None:
    cases = _load_fixture()
    for case in cases:
        text = case["input_text"]
        assert (
            isinstance(text, str) and text.strip()
        ), f"case {case['id']!r} has empty input_text"
        # Sanity check: at least one Hangul codepoint per case.
        assert any(
            "가" <= ch <= "힣" for ch in text
        ), f"case {case['id']!r} input_text has no Hangul: {text!r}"


def test_fixture_ids_are_unique() -> None:
    cases = _load_fixture()
    ids = [case["id"] for case in cases]
    assert len(ids) == len(set(ids)), "duplicate case ids in fixture"


def test_fixture_has_minimum_category_coverage() -> None:
    """Every category in the eval set must be represented.

    Prevents accidental category drift when editorial updates remove
    cases (FR-032 — every guardrail layer must remain testable across
    all four user-facing categories + the general bucket).
    """
    cases = _load_fixture()
    seen = {case["category_tag"] for case in cases}
    assert (
        seen == _ALLOWED_CATEGORIES
    ), f"fixture missing categories: {_ALLOWED_CATEGORIES - seen}"


def test_fixture_has_minimum_violation_coverage() -> None:
    """Violation cases must cover every severity label.

    Layer-3 (deny-list) must catch both ``violation_mild`` and
    ``violation_severe`` rows — if the fixture only contained one
    severity, the harness could pass while the other severity is
    completely untested.
    """
    cases = _load_fixture()
    violation_labels = {
        case["expected_label"] for case in cases if case["case_kind"] == "violation"
    }
    assert violation_labels >= {
        "violation_mild",
        "violation_severe",
    }, f"violation severity coverage incomplete: {violation_labels}"


# ---------------------------------------------------------------------------
# 2) Deny-list correctness gate — runs only when ISSUE-020 module exists.
# ---------------------------------------------------------------------------


@pytest.mark.tone_regression
def test_denylist_blocks_all_violations() -> None:
    """ISSUE-020 deliverable: every ``violation`` case must trip the
    deny-list (``substitute`` or ``block``). 100% threshold.
    """
    denylist = pytest.importorskip(
        "voicesaju.llm.guardrail.denylist",
        reason="ISSUE-020 deny-list module not yet implemented",
    )

    cases = _load_fixture()
    violations = [c for c in cases if c["case_kind"] == "violation"]
    assert violations, "no violation cases in fixture"

    missed: list[str] = []
    for case in violations:
        result = denylist.filter_chunk(case["input_text"])
        action = getattr(result, "action", None)
        if action not in ("substitute", "block"):
            missed.append(case["id"])

    block_rate = 1.0 - (len(missed) / len(violations))
    assert block_rate >= _VIOLATION_BLOCK_RATE, (
        f"deny-list missed {len(missed)} violation case(s) "
        f"({block_rate:.2%} < {_VIOLATION_BLOCK_RATE:.0%}): {missed}"
    )


@pytest.mark.tone_regression
def test_denylist_preserves_clean_cases() -> None:
    """ISSUE-020 deliverable: ≥ 95% of clean ``ok`` cases pass
    unmodified. False positives below this rate would degrade reading
    quality.
    """
    denylist = pytest.importorskip(
        "voicesaju.llm.guardrail.denylist",
        reason="ISSUE-020 deny-list module not yet implemented",
    )

    cases = _load_fixture()
    oks = [c for c in cases if c["case_kind"] == "ok"]
    assert oks, "no ok cases in fixture"

    over_triggered: list[str] = []
    for case in oks:
        result = denylist.filter_chunk(case["input_text"])
        action = getattr(result, "action", None)
        if action != "pass":
            over_triggered.append(case["id"])

    preserve_rate = 1.0 - (len(over_triggered) / len(oks))
    assert preserve_rate >= _OK_PRESERVE_RATE, (
        f"deny-list over-triggered on {len(over_triggered)} ok case(s) "
        f"({preserve_rate:.2%} < {_OK_PRESERVE_RATE:.0%}): {over_triggered}"
    )


@pytest.mark.tone_regression
def test_denylist_does_not_over_trigger_on_spicy_borderline() -> None:
    """ISSUE-020 deliverable: ``spicy_ok`` cases (e.g. "매운맛 흐름이에요")
    must pass — they test that the deny-list does not over-trigger on
    figurative or "spicy" Korean expressions that are *not* profanity.
    """
    denylist = pytest.importorskip(
        "voicesaju.llm.guardrail.denylist",
        reason="ISSUE-020 deny-list module not yet implemented",
    )

    cases = _load_fixture()
    spicy = [c for c in cases if c["case_kind"] == "spicy_ok"]
    assert spicy, "no spicy_ok cases in fixture"

    blocked: list[str] = []
    for case in spicy:
        result = denylist.filter_chunk(case["input_text"])
        action = getattr(result, "action", None)
        if action != "pass":
            blocked.append(case["id"])

    preserve_rate = 1.0 - (len(blocked) / len(spicy))
    assert preserve_rate >= _OK_PRESERVE_RATE, (
        f"deny-list blocked {len(blocked)} spicy_ok case(s) "
        f"({preserve_rate:.2%} < {_OK_PRESERVE_RATE:.0%}): {blocked}"
    )
