"""Regression suite for :func:`voicesaju.saju.engine.compute_chart`.

Loads ``tests/fixtures/saju_known_cases.json`` (≥50 entries — see
ISSUE-012) and runs every case 3× per pytest invocation, asserting:

1. **Determinism (NFR-017)** — the three runs return byte-identical
   :class:`SajuChart` dicts (and matching ``chart_hash``).
2. **Match expected** — the engine output equals the JSON-encoded
   ``expected`` value, so a refactor that alters any seeded pillar (year,
   month, day, hour stem/branch/element) fails CI.

The suite is marked with ``@pytest.mark.regression`` and is included in
the default pytest run (the ``addopts = "-m 'not integration'"`` filter
does not exclude it).
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import datetime
from pathlib import Path

import pytest

from voicesaju.saju import compute_chart

FIXTURE_PATH = (
    Path(__file__).resolve().parent.parent / "fixtures" / "saju_known_cases.json"
)

# Mix requirements echo the ISSUE-012 spec — keep them in sync if the
# fixture distribution changes.
_MIN_TOTAL = 50
_MIN_SOLAR = 25
_MIN_LUNAR = 25
_MIN_TIME_UNKNOWN = 10


def _load_fixtures() -> list[dict]:
    if not FIXTURE_PATH.exists():
        raise FileNotFoundError(
            f"saju regression fixtures missing at {FIXTURE_PATH}; "
            "run `uv run python scripts/generate_saju_fixtures.py` to "
            "regenerate."
        )
    payload = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    fixtures = payload["fixtures"]
    assert isinstance(fixtures, list), "fixtures payload must be a list"
    return fixtures


def _iter_cases() -> Iterator[tuple[str, dict]]:
    for i, case in enumerate(_load_fixtures()):
        yield f"case-{i + 1:03d}-{case['birth_dt']}", case


# Materialize once so collection-time ID generation matches what pytest
# uses for the parametrize. The list also lets the mix-requirement test
# below operate on the same source of truth.
_CASES: list[tuple[str, dict]] = list(_iter_cases())


@pytest.mark.regression
def test_fixture_count_meets_minimum() -> None:
    """≥50 cases with the mix required by the ISSUE-012 spec."""

    fixtures = _load_fixtures()
    total = len(fixtures)
    solar = sum(1 for f in fixtures if not f["is_lunar"])
    lunar = sum(1 for f in fixtures if f["is_lunar"])
    time_unknown = sum(1 for f in fixtures if f["time_unknown"])

    assert total >= _MIN_TOTAL, f"only {total} fixtures (<{_MIN_TOTAL})"
    assert solar >= _MIN_SOLAR, f"only {solar} solar (<{_MIN_SOLAR})"
    assert lunar >= _MIN_LUNAR, f"only {lunar} lunar (<{_MIN_LUNAR})"
    assert (
        time_unknown >= _MIN_TIME_UNKNOWN
    ), f"only {time_unknown} time_unknown (<{_MIN_TIME_UNKNOWN})"


@pytest.mark.regression
@pytest.mark.parametrize(("label", "case"), _CASES, ids=[c[0] for c in _CASES])
def test_compute_chart_matches_fixture_and_is_deterministic(
    label: str,
    case: dict,
) -> None:
    """3 runs of the engine on the same fixture must match each other and the JSON."""

    del label  # used only for the test id
    birth_dt = datetime.fromisoformat(case["birth_dt"])
    runs = [
        compute_chart(
            birth_dt,
            is_lunar=case["is_lunar"],
            gender=case["gender"],
            time_unknown=case["time_unknown"],
        )
        for _ in range(3)
    ]

    first = runs[0]
    # Determinism: every additional run is byte-identical.
    for other in runs[1:]:
        assert other == first
        assert other.chart_hash == first.chart_hash
        assert other.to_dict() == first.to_dict()

    # Match expected (canonical dict form).
    expected = case["expected"]
    actual = {
        "year": first.year.to_dict(),
        "month": first.month.to_dict(),
        "day": first.day.to_dict(),
        "hour": first.hour.to_dict() if first.hour else None,
        "chart_hash": first.chart_hash,
        "engine_version": first.engine_version,
    }
    assert actual == expected, (
        f"engine output diverged from fixture for {case['birth_dt']}: "
        f"actual={actual}, expected={expected}"
    )
