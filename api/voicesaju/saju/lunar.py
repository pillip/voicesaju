"""Lunar ↔ solar (양력/음력) conversion helpers.

Wraps :mod:`korean_lunar_calendar` when available. Falls back to a
static lookup table for a small set of well-known dates so unit tests
remain deterministic even on hosts that have not yet installed the
optional dependency.
"""

from __future__ import annotations

from datetime import date

# Static table of (lunar_year, lunar_month, lunar_day, is_leap_month) →
# Gregorian (solar) date. Used as a fallback when
# `korean_lunar_calendar` is unavailable. Sourced from KASI (한국천문연구원)
# 음력↔양력 변환표.
_LUNAR_SOLAR_FALLBACK: dict[tuple[int, int, int, bool], date] = {
    # 음력 1990-01-01 (설날) → 양력 1990-01-27
    (1990, 1, 1, False): date(1990, 1, 27),
    # 음력 2000-01-01 → 양력 2000-02-05
    (2000, 1, 1, False): date(2000, 2, 5),
    # 음력 2024-01-01 → 양력 2024-02-10
    (2024, 1, 1, False): date(2024, 2, 10),
    # 음력 1995-08-15 (추석) → 양력 1995-09-09
    (1995, 8, 15, False): date(1995, 9, 9),
}


def lunar_to_solar(
    year: int,
    month: int,
    day: int,
    *,
    is_leap: bool = False,
) -> date:
    """Convert a Korean lunar date to its Gregorian (solar) counterpart.

    Tries the :mod:`korean_lunar_calendar` library first, then falls back
    to a small static table for a few well-known dates. Raises
    :class:`ValueError` if neither path can resolve the input.
    """

    try:  # pragma: no cover - exercised only when the optional dep is installed
        from korean_lunar_calendar import KoreanLunarCalendar

        cal = KoreanLunarCalendar()
        # The library returns False if the lunar date is invalid.
        if cal.setLunarDate(year, month, day, is_leap):
            solar = cal.SolarIsoFormat()  # "YYYY-MM-DD"
            y, m, d = (int(part) for part in solar.split("-"))
            return date(y, m, d)
    except ImportError:  # pragma: no cover - install fallback path
        pass

    key = (year, month, day, is_leap)
    if key in _LUNAR_SOLAR_FALLBACK:
        return _LUNAR_SOLAR_FALLBACK[key]

    raise ValueError(
        f"lunar_to_solar: unable to convert {year}-{month:02d}-{day:02d} "
        f"(is_leap={is_leap}) — install `korean-lunar-calendar` "
        "for full coverage."
    )
