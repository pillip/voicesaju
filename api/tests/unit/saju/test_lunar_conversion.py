"""Lunar → solar conversion smoke tests for the Saju engine.

Verifies that `compute_chart(is_lunar=True, ...)` triggers a lunar
conversion via `voicesaju.saju.lunar.lunar_to_solar` and that the
resulting chart matches the one produced from the equivalent solar date.
"""

from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest

from voicesaju.saju import compute_chart
from voicesaju.saju.lunar import lunar_to_solar

KST = ZoneInfo("Asia/Seoul")


# Known lunar→solar pairs (from the static fallback table in lunar.py).
_KNOWN_PAIRS: list[tuple[date, date]] = [
    # 음력 1990-01-01 (설날) → 양력 1990-01-27
    (date(1990, 1, 1), date(1990, 1, 27)),
    # 음력 2000-01-01 → 양력 2000-02-05
    (date(2000, 1, 1), date(2000, 2, 5)),
]


@pytest.mark.parametrize(("lunar_dt", "expected_solar"), _KNOWN_PAIRS)
def test_lunar_to_solar_known_pairs(lunar_dt: date, expected_solar: date) -> None:
    """Static-table fallback returns the documented solar dates."""

    got = lunar_to_solar(lunar_dt.year, lunar_dt.month, lunar_dt.day)
    assert got == expected_solar


def test_compute_chart_with_lunar_input_routes_through_lunar_conversion() -> None:
    """`is_lunar=True` must yield the same chart as the equivalent solar input.

    음력 1990-01-01 12:00 ≡ 양력 1990-01-27 12:00 — both inputs must produce
    the same year/month/day/hour pillars.
    """

    lunar_dt = datetime(1990, 1, 1, 12, 0, tzinfo=KST)
    solar_equivalent = datetime(1990, 1, 27, 12, 0, tzinfo=KST)

    lunar_chart = compute_chart(
        lunar_dt, is_lunar=True, gender="male", time_unknown=False
    )
    solar_chart = compute_chart(
        solar_equivalent, is_lunar=False, gender="male", time_unknown=False
    )

    assert lunar_chart == solar_chart
    assert lunar_chart.chart_hash == solar_chart.chart_hash
