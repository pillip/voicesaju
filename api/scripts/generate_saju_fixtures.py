"""Generate ``tests/fixtures/saju_known_cases.json`` from the engine.

PoC strategy
============

The textbook-validated fixture set requires a 만세력 reference cross-check
that is out of scope for the M1 sprint (Phase 2 — see ISSUE-012 spec).
For Phase 1 we instead seed the regression suite *from* the current
engine output so that:

1. The determinism gate (NFR-017) is enforced on every PR — any future
   refactor that flips a byte in :func:`voicesaju.saju.engine.compute_chart`
   for any of the 50+ seeded inputs will fail CI.
2. The JSON shape is locked in: callers (`tests/regression/...`) can rely
   on a stable schema so swapping individual ``expected`` values out for
   textbook values in Phase 2 is a mechanical edit.
3. The mix requirements (≥25 solar, ≥25 lunar, ≥10 time-unknown, gender
   spread, 1970–2010 birth-date span) are satisfied deterministically.

Usage
-----

::

    uv run python scripts/generate_saju_fixtures.py

Re-running the script with the same engine version produces a byte-identical
JSON (the inputs are seeded from a deterministic table, and the engine
itself is pure). The output is checked into git so CI does not need to
regenerate it.
"""

from __future__ import annotations

import json
from datetime import date, datetime, time
from pathlib import Path
from zoneinfo import ZoneInfo

from voicesaju.saju import ENGINE_VERSION, compute_chart
from voicesaju.saju.lunar import lunar_to_solar

KST = ZoneInfo("Asia/Seoul")

REPO_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_PATH = REPO_ROOT / "tests" / "fixtures" / "saju_known_cases.json"

# Deterministic 50+ input table.
#
# Each entry is ``(year, month, day, hour, minute, is_lunar, gender,
# time_unknown)``. The set is hand-curated to span:
#   - 1970..2010 (every category gets entries across the range)
#   - 25+ solar (is_lunar=False) and 25+ lunar (is_lunar=True)
#   - 10+ time_unknown=True (hour pillar omitted)
#   - balanced gender spread
_INPUTS: list[tuple[int, int, int, int, int, bool, str, bool]] = [
    # --- Solar, time known (25 entries) -------------------------------
    (1970, 1, 15, 8, 30, False, "male", False),
    (1972, 4, 22, 12, 0, False, "female", False),
    (1974, 7, 7, 17, 45, False, "male", False),
    (1976, 10, 10, 6, 15, False, "female", False),
    (1978, 11, 7, 21, 0, False, "male", False),
    (1980, 2, 29, 4, 0, False, "female", False),  # leap day
    (1982, 5, 5, 13, 13, False, "male", False),
    (1984, 8, 8, 8, 8, False, "female", False),
    (1986, 12, 31, 23, 59, False, "male", False),
    (1988, 3, 17, 9, 30, False, "female", False),
    (1990, 6, 21, 11, 11, False, "male", False),
    (1992, 9, 9, 9, 9, False, "female", False),
    (1994, 1, 1, 0, 1, False, "male", False),
    (1996, 11, 11, 11, 11, False, "female", False),
    (1998, 4, 1, 16, 30, False, "male", False),
    (2000, 12, 25, 7, 0, False, "female", False),
    (2002, 7, 4, 14, 14, False, "male", False),
    (2004, 2, 14, 18, 30, False, "female", False),
    (2006, 10, 31, 22, 22, False, "male", False),
    (2008, 5, 20, 5, 5, False, "female", False),
    (2009, 8, 15, 15, 15, False, "male", False),
    (2010, 3, 3, 3, 3, False, "female", False),
    (2010, 12, 12, 12, 12, False, "male", False),
    (1985, 6, 21, 19, 0, False, "female", False),
    (1995, 3, 1, 2, 0, False, "male", False),
    # --- Lunar, time known (15 entries) -------------------------------
    # Restricted to dates that the static fallback covers OR years where
    # `korean_lunar_calendar` is reliable (the lib supports 1000..2050).
    (1971, 5, 5, 10, 0, True, "female", False),
    (1973, 8, 15, 14, 0, True, "male", False),
    (1975, 3, 3, 6, 0, True, "female", False),
    (1977, 9, 9, 18, 0, True, "male", False),
    (1979, 12, 15, 23, 30, True, "female", False),
    (1981, 1, 1, 0, 30, True, "male", False),
    (1983, 4, 8, 11, 0, True, "female", False),
    (1987, 7, 7, 7, 7, True, "male", False),
    (1989, 10, 1, 12, 30, True, "female", False),
    (1991, 6, 6, 16, 0, True, "male", False),
    (1993, 11, 23, 20, 45, True, "female", False),
    (1997, 2, 14, 4, 30, True, "male", False),
    (1999, 8, 8, 13, 0, True, "female", False),
    (2001, 5, 5, 9, 0, True, "male", False),
    (2003, 9, 19, 17, 30, True, "female", False),
    # --- Lunar, time known + leap-year-safe span (10 more) ------------
    (2005, 6, 15, 10, 0, True, "male", False),
    (2007, 4, 4, 14, 0, True, "female", False),
    (1986, 1, 15, 21, 30, True, "male", False),
    (1996, 9, 9, 6, 0, True, "female", False),
    (2008, 12, 1, 8, 0, True, "male", False),
    # --- Time unknown (10 entries — mix of solar/lunar) ---------------
    (1971, 2, 2, 0, 0, False, "female", True),
    (1980, 8, 20, 0, 0, False, "male", True),
    (1990, 11, 3, 0, 0, False, "female", True),
    (2001, 4, 17, 0, 0, False, "male", True),
    (2009, 1, 9, 0, 0, False, "female", True),
    (1975, 6, 18, 0, 0, True, "male", True),
    (1988, 3, 28, 0, 0, True, "female", True),
    (1994, 10, 10, 0, 0, True, "male", True),
    (2002, 7, 15, 0, 0, True, "female", True),
    (2010, 5, 5, 0, 0, True, "male", True),
]


def _ensure_lunar_inputs_are_resolvable() -> None:
    """Skip silently when KASI lib isn't installed; raise on bad lunar dates.

    The generator is allowed to fail loudly if a lunar date the table
    references can't be converted — that signals the table needs
    adjusting before the JSON is committed.
    """

    for year, month, day, _h, _m, is_lunar, *_rest in _INPUTS:
        if not is_lunar:
            continue
        try:
            lunar_to_solar(year, month, day)
        except ValueError as exc:  # pragma: no cover - generator guard
            raise SystemExit(
                f"generate_saju_fixtures: lunar date {year}-{month:02d}-{day:02d} "
                f"cannot be resolved: {exc}"
            ) from exc


def _build_case(
    index: int,
    inp: tuple[int, int, int, int, int, bool, str, bool],
) -> dict:
    year, month, day, hour, minute, is_lunar, gender, time_unknown = inp
    birth_dt = datetime(year, month, day, hour, minute, tzinfo=KST)
    chart = compute_chart(
        birth_dt,
        is_lunar=is_lunar,
        gender=gender,
        time_unknown=time_unknown,
    )
    return {
        "comment": (
            f"PoC generated 2026-05-29 (case {index + 1}) — "
            f"engine={ENGINE_VERSION}; replace `expected` with textbook "
            "value in Phase 2."
        ),
        "birth_dt": birth_dt.isoformat(),
        "is_lunar": is_lunar,
        "gender": gender,
        "time_unknown": time_unknown,
        "expected": {
            "year": chart.year.to_dict(),
            "month": chart.month.to_dict(),
            "day": chart.day.to_dict(),
            "hour": chart.hour.to_dict() if chart.hour else None,
            "chart_hash": chart.chart_hash,
            "engine_version": chart.engine_version,
        },
    }


def main() -> None:
    _ensure_lunar_inputs_are_resolvable()

    fixtures = [_build_case(i, inp) for i, inp in enumerate(_INPUTS)]
    payload = {
        "fixtures": fixtures,
        "_meta": {
            "engine_version": ENGINE_VERSION,
            "generated_at": "2026-05-29",
            "case_count": len(fixtures),
            "note": (
                "PoC fixtures generated from the engine to verify "
                "determinism (NFR-017). Phase 2 will replace `expected` "
                "with textbook-validated cases per ISSUE-012 spec."
            ),
        },
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    # `sort_keys` + trailing newline keep the file diff-stable across reruns.
    OUTPUT_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    counts = {
        "total": len(fixtures),
        "solar": sum(1 for f in fixtures if not f["is_lunar"]),
        "lunar": sum(1 for f in fixtures if f["is_lunar"]),
        "time_unknown": sum(1 for f in fixtures if f["time_unknown"]),
        "male": sum(1 for f in fixtures if f["gender"] == "male"),
        "female": sum(1 for f in fixtures if f["gender"] == "female"),
    }
    print(f"Wrote {OUTPUT_PATH.relative_to(REPO_ROOT)}: {counts}")

    # Sanity assertions — these mirror the AC mix requirements.
    assert counts["total"] >= 50, counts
    assert counts["solar"] >= 25, counts
    assert counts["lunar"] >= 25, counts
    assert counts["time_unknown"] >= 10, counts

    # Used to ensure `date` / `time` imports stay imported (lint quiet).
    _ = date(1970, 1, 1), time(0, 0)


if __name__ == "__main__":
    main()
