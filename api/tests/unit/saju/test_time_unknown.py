"""`time_unknown=True` behavior tests for the Saju engine."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from voicesaju.saju import compute_chart

KST = ZoneInfo("Asia/Seoul")


def test_time_unknown_returns_three_pillars() -> None:
    """When the birth time is unknown, `hour` must be None and 3 pillars set."""

    chart = compute_chart(
        datetime(1995, 3, 15, 7, 30, tzinfo=KST),
        is_lunar=False,
        gender="male",
        time_unknown=True,
    )
    assert chart.hour is None
    assert chart.year is not None
    assert chart.month is not None
    assert chart.day is not None


def test_time_known_returns_four_pillars() -> None:
    """When the birth time is provided, all 4 pillars must be populated."""

    chart = compute_chart(
        datetime(1995, 3, 15, 7, 30, tzinfo=KST),
        is_lunar=False,
        gender="male",
        time_unknown=False,
    )
    assert chart.hour is not None
    assert chart.year is not None
    assert chart.month is not None
    assert chart.day is not None
    # Every pillar must carry a stem, branch, and element.
    for pillar in (chart.year, chart.month, chart.day, chart.hour):
        assert pillar.stem is not None
        assert pillar.branch is not None
        assert pillar.element is not None


def test_time_unknown_hour_independence() -> None:
    """When `time_unknown=True`, the input hour must not affect the chart hash.

    Two calls with different hour-of-day but the same date/`time_unknown=True`
    flag must produce identical charts — the hour pillar is dropped from the
    canonical hash payload.
    """

    base_date = (1990, 5, 20)
    a = compute_chart(
        datetime(*base_date, 3, 0, tzinfo=KST),
        is_lunar=False,
        gender="male",
        time_unknown=True,
    )
    b = compute_chart(
        datetime(*base_date, 18, 45, tzinfo=KST),
        is_lunar=False,
        gender="male",
        time_unknown=True,
    )
    assert a.chart_hash == b.chart_hash
