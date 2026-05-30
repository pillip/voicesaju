"""ISSUE-034 — Cost tracker token + KRW accounting.

Tests Acceptance Criteria #5:
- Given a successful call, when complete, then cost_tracker records
  `input_tokens`, `output_tokens`, `total_krw`.

Plus the broader contract from Architecture §7.4:
- Per-call record has `model`, `input_tokens`, `output_tokens`,
  `unit_price_in`, `unit_price_out`, `total_krw`.
- Multiple records aggregate into `Reading.cost_krw`.

The tracker is process-local + in-memory. Persistence to `Reading.cost_krw`
is the caller's responsibility (pipeline orchestration in ISSUE-039) —
this module just provides the math + audit list.
"""

from __future__ import annotations

import pytest

from voicesaju.llm.cost_tracker import (
    CostRecord,
    CostTracker,
    compute_call_krw,
)
from voicesaju.llm.router import HAIKU_4_5, SONNET_4_6

# ---------------------------------------------------------------------------
# compute_call_krw — pure pricing function
# ---------------------------------------------------------------------------


class TestComputeCallKrw:
    """Pure arithmetic — easy to lock down and easy to refactor."""

    def test_basic_math(self) -> None:
        """1k input + 1k output at 4 KRW/1k + 20 KRW/1k → 24 KRW total.

        Using rounded numbers makes the assertion obvious; the production
        rates come from `Settings` so this test pins only the formula.
        """
        krw = compute_call_krw(
            input_tokens=1_000,
            output_tokens=1_000,
            input_krw_per_mtok=4_000.0,
            output_krw_per_mtok=20_000.0,
        )
        # 1k tokens / 1M tokens = 0.001 → 0.001 * 4000 = 4.0
        #                                + 0.001 * 20000 = 20.0
        assert krw == pytest.approx(24.0)

    def test_zero_tokens_costs_zero(self) -> None:
        krw = compute_call_krw(
            input_tokens=0,
            output_tokens=0,
            input_krw_per_mtok=4_000.0,
            output_krw_per_mtok=20_000.0,
        )
        assert krw == 0.0

    def test_negative_tokens_raises(self) -> None:
        """Token counts are unsigned by definition — bug if negative leaks
        through from the SDK."""
        with pytest.raises(ValueError):
            compute_call_krw(
                input_tokens=-1,
                output_tokens=0,
                input_krw_per_mtok=4_000.0,
                output_krw_per_mtok=20_000.0,
            )
        with pytest.raises(ValueError):
            compute_call_krw(
                input_tokens=0,
                output_tokens=-1,
                input_krw_per_mtok=4_000.0,
                output_krw_per_mtok=20_000.0,
            )

    def test_sonnet_vs_haiku_proportional(self) -> None:
        """Sanity: at the same token count, Sonnet must cost more than
        Haiku given Anthropic's published price ordering. We pick a
        Sonnet rate 5× Haiku to model the gap conservatively."""
        cheap = compute_call_krw(
            input_tokens=10_000,
            output_tokens=10_000,
            input_krw_per_mtok=1_000.0,
            output_krw_per_mtok=5_000.0,
        )
        expensive = compute_call_krw(
            input_tokens=10_000,
            output_tokens=10_000,
            input_krw_per_mtok=5_000.0,
            output_krw_per_mtok=25_000.0,
        )
        assert expensive == pytest.approx(cheap * 5)


# ---------------------------------------------------------------------------
# CostTracker — in-memory aggregator
# ---------------------------------------------------------------------------


class TestCostTrackerRecord:
    """AC #5: tracker records input/output tokens + KRW per call."""

    def test_records_a_single_call(self) -> None:
        tracker = CostTracker()
        tracker.record(
            model=SONNET_4_6,
            input_tokens=1_500,
            output_tokens=1_200,
            input_krw_per_mtok=4_000.0,
            output_krw_per_mtok=20_000.0,
        )
        assert len(tracker.records) == 1
        rec = tracker.records[0]
        assert isinstance(rec, CostRecord)
        assert rec.model == SONNET_4_6
        assert rec.input_tokens == 1_500
        assert rec.output_tokens == 1_200
        # 1500/1M*4000 + 1200/1M*20000 = 6 + 24 = 30
        assert rec.total_krw == pytest.approx(30.0)
        # Per-call unit prices preserved for audit / cost-model dashboards.
        assert rec.unit_price_in == 4_000.0
        assert rec.unit_price_out == 20_000.0

    def test_records_multiple_calls(self) -> None:
        """A reading is one Sonnet main + ≥1 Haiku follow-up; tracker must
        keep them as separate records so the per-model rollup works."""
        tracker = CostTracker()
        tracker.record(
            model=SONNET_4_6,
            input_tokens=1_500,
            output_tokens=1_200,
            input_krw_per_mtok=4_000.0,
            output_krw_per_mtok=20_000.0,
        )
        tracker.record(
            model=HAIKU_4_5,
            input_tokens=800,
            output_tokens=450,
            input_krw_per_mtok=1_000.0,
            output_krw_per_mtok=5_000.0,
        )
        assert len(tracker.records) == 2
        assert tracker.records[0].model == SONNET_4_6
        assert tracker.records[1].model == HAIKU_4_5

    def test_total_krw_sums_all_records(self) -> None:
        tracker = CostTracker()
        tracker.record(
            model=SONNET_4_6,
            input_tokens=1_000,
            output_tokens=1_000,
            input_krw_per_mtok=4_000.0,
            output_krw_per_mtok=20_000.0,
        )
        tracker.record(
            model=HAIKU_4_5,
            input_tokens=1_000,
            output_tokens=1_000,
            input_krw_per_mtok=1_000.0,
            output_krw_per_mtok=5_000.0,
        )
        # 24 + 6 = 30
        assert tracker.total_krw() == pytest.approx(30.0)

    def test_total_tokens_sums_each_kind(self) -> None:
        tracker = CostTracker()
        tracker.record(
            model=SONNET_4_6,
            input_tokens=1_500,
            output_tokens=1_200,
            input_krw_per_mtok=4_000.0,
            output_krw_per_mtok=20_000.0,
        )
        tracker.record(
            model=HAIKU_4_5,
            input_tokens=800,
            output_tokens=450,
            input_krw_per_mtok=1_000.0,
            output_krw_per_mtok=5_000.0,
        )
        assert tracker.total_input_tokens() == 2_300
        assert tracker.total_output_tokens() == 1_650

    def test_empty_tracker_totals_zero(self) -> None:
        tracker = CostTracker()
        assert tracker.records == []
        assert tracker.total_krw() == 0.0
        assert tracker.total_input_tokens() == 0
        assert tracker.total_output_tokens() == 0
