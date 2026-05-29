"""Determinism (NFR-017) tests for `voicesaju.saju.engine.compute_chart`.

The engine must produce byte-identical output for identical inputs across
repeated invocations. We sample 10 diverse birth datetimes and run the
engine 3 times per case, asserting both the high-level :class:`SajuChart`
and the canonical `chart_hash` are stable.
"""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from voicesaju.saju import SajuChart, compute_chart

KST = ZoneInfo("Asia/Seoul")

_CASES: list[tuple[datetime, bool, str, bool]] = [
    (datetime(1990, 1, 15, 8, 30, tzinfo=KST), False, "male", False),
    (datetime(1985, 6, 21, 13, 15, tzinfo=KST), False, "female", False),
    (datetime(2000, 12, 31, 23, 59, tzinfo=KST), False, "male", False),
    (datetime(1995, 3, 1, 4, 0, tzinfo=KST), False, "female", False),
    (datetime(1978, 11, 7, 17, 45, tzinfo=KST), False, "male", False),
    (datetime(2005, 7, 4, 0, 1, tzinfo=KST), False, "female", False),
    (datetime(1969, 9, 9, 9, 9, tzinfo=KST), False, "male", False),
    (datetime(2010, 2, 14, 12, 0, tzinfo=KST), False, "female", True),
    (datetime(1992, 5, 5, 6, 30, tzinfo=KST), False, "male", True),
    (datetime(1988, 8, 8, 8, 8, tzinfo=KST), False, "female", False),
]


@pytest.mark.parametrize(
    ("birth_dt", "is_lunar", "gender", "time_unknown"),
    _CASES,
    ids=[c[0].isoformat() for c in _CASES],
)
def test_compute_chart_is_deterministic(
    birth_dt: datetime,
    is_lunar: bool,
    gender: str,
    time_unknown: bool,
) -> None:
    """3 runs of the same input must return identical chart + hash."""

    runs: list[SajuChart] = [
        compute_chart(
            birth_dt,
            is_lunar=is_lunar,
            gender=gender,
            time_unknown=time_unknown,
        )
        for _ in range(3)
    ]
    first = runs[0]
    for other in runs[1:]:
        assert other == first
        assert other.chart_hash == first.chart_hash
        assert other.to_dict() == first.to_dict()
