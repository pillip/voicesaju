"""Pure-function Saju (사주) calculation engine.

Computes a deterministic 4-pillar 명식 (:class:`SajuChart`) from a birth
datetime. The engine is intentionally pure — no DB I/O, no globals — so
identical inputs always produce a byte-identical output (NFR-017).

Algorithm (V1 PoC)
------------------
This implementation uses a *simplified* 60-갑자 arithmetic mapping rather
than the textbook 만세력 (manseryeok) tables, because the `manseryeok`
package is not yet available on PyPI. The simplification is acceptable
for the M1 foundation work:

- Year pillar is the 60-갑자 of the solar year, with the cycle anchored on
  1984 = 갑자(甲子)년 — a widely used epoch in Korean almanacs.
- Month / day / hour pillars follow the standard derivation rules:
  - Month stem is determined by the year stem + lunar month index.
  - Day pillar is the 60-갑자 of the day, anchored on a known reference
    date (1900-01-01 = 갑술(甲戌)일, day index 10 in the cycle).
  - Hour stem is determined by the day stem + 시지 (hour branch).

ISSUE-012 will validate accuracy against ≥50 textbook cases and either
confirm the simplified math or swap in a richer table-driven engine.
"""

from __future__ import annotations

import hashlib
import json
from datetime import date, datetime

from voicesaju.saju.lunar import lunar_to_solar
from voicesaju.saju.models import (
    BRANCH_ELEMENT,
    BRANCHES_ORDER,
    STEM_ELEMENT,
    STEMS_ORDER,
    Branch,
    Pillar,
    SajuChart,
    Stem,
)

ENGINE_VERSION = "saju.v1.2026-05"

# Reference epoch: 1900-01-01 (Gregorian) corresponds to day index 10 in
# the 60-갑자 cycle (갑술/甲戌). Sourced from KASI almanac cross-check.
_DAY_EPOCH = date(1900, 1, 1)
_DAY_EPOCH_INDEX = 10

# Reference epoch: 1984 (Gregorian) = 갑자(甲子)년 — index 0 in 60-갑자.
_YEAR_EPOCH = 1984
_YEAR_EPOCH_INDEX = 0


def _stem_at(index: int) -> Stem:
    """Return the stem at position ``index`` in the 10-stem cycle."""

    return STEMS_ORDER[index % 10]


def _branch_at(index: int) -> Branch:
    """Return the branch at position ``index`` in the 12-branch cycle."""

    return BRANCHES_ORDER[index % 12]


def _make_pillar(stem: Stem, branch: Branch) -> Pillar:
    return Pillar(
        stem=stem,
        branch=branch,
        element=STEM_ELEMENT[stem],
    )


def _year_pillar(solar_year: int) -> Pillar:
    """Compute the year pillar using the 60-갑자 cycle anchored at 1984."""

    offset = solar_year - _YEAR_EPOCH
    cycle_index = (offset + _YEAR_EPOCH_INDEX) % 60
    return _make_pillar(_stem_at(cycle_index), _branch_at(cycle_index))


def _month_pillar(year_pillar: Pillar, solar_month: int) -> Pillar:
    """Compute the month pillar from year stem + lunar month index.

    Uses the standard 月柱 derivation rule:
      - Year stems 갑/기 → 인(寅) month starts at 병(丙)
      - Year stems 을/경 → 인(寅) month starts at 무(戊)
      - Year stems 병/신 → 인(寅) month starts at 경(庚)
      - Year stems 정/임 → 인(寅) month starts at 임(壬)
      - Year stems 무/계 → 인(寅) month starts at 갑(甲)
    """

    year_stem_index = STEMS_ORDER.index(year_pillar.stem)
    # 갑/기→0,을/경→1,병/신→2,정/임→3,무/계→4 — starting stem index for 인月.
    inwol_start_table = {0: 2, 5: 2, 1: 4, 6: 4, 2: 6, 7: 6, 3: 8, 8: 8, 4: 0, 9: 0}
    inwol_start = inwol_start_table[year_stem_index]

    # Month branch: 인(寅)=정월 (lunar month 1 in solar terms convention).
    # We map solar month 1..12 → 子,축,...,해 starting at 인(2):
    # solar month 1 (January) ≈ 축(丑), 2 ≈ 인(寅);
    # branch_index = (solar_month + 1) % 12.
    # Lunar 寅月 (lunar month 1) corresponds to roughly Feb in solar terms.
    branch_index = (solar_month + 1) % 12
    # Months past 寅 within the year are counted from 0:
    months_from_in = (solar_month + 11) % 12  # Feb→0,Mar→1,...,Jan→11
    stem_index = (inwol_start + months_from_in) % 10

    return _make_pillar(_stem_at(stem_index), _branch_at(branch_index))


def _day_pillar(solar_date: date) -> Pillar:
    """Compute the day pillar via the 60-갑자 cycle anchored at 1900-01-01."""

    delta_days = (solar_date - _DAY_EPOCH).days
    cycle_index = (delta_days + _DAY_EPOCH_INDEX) % 60
    return _make_pillar(_stem_at(cycle_index), _branch_at(cycle_index))


def _hour_pillar(day_pillar: Pillar, hour: int) -> Pillar:
    """Compute the hour pillar from day stem + hour-of-day.

    Hour branches map to 2-hour blocks (자/子=23-01, 축=01-03, …).
    The hour stem follows the 五子遁 rule:
      - Day stems 갑/기 → 자(子) hour starts at 갑(甲)
      - Day stems 을/경 → 자(子) hour starts at 병(丙)
      - Day stems 병/신 → 자(子) hour starts at 무(戊)
      - Day stems 정/임 → 자(子) hour starts at 경(庚)
      - Day stems 무/계 → 자(子) hour starts at 임(壬)
    """

    # Hour → branch index (자=0 covers 23–01, 축=1 covers 01–03, …).
    # We map hour-of-day (0..23) by ``((h + 1) // 2) % 12``.
    branch_index = ((hour + 1) // 2) % 12

    day_stem_index = STEMS_ORDER.index(day_pillar.stem)
    # 갑/기→0,을/경→2,병/신→4,정/임→6,무/계→8 starting stem index for 자時.
    jasi_start_table = {0: 0, 5: 0, 1: 2, 6: 2, 2: 4, 7: 4, 3: 6, 8: 6, 4: 8, 9: 8}
    jasi_start = jasi_start_table[day_stem_index]

    stem_index = (jasi_start + branch_index) % 10
    stem = _stem_at(stem_index)
    branch = _branch_at(branch_index)
    return Pillar(stem=stem, branch=branch, element=BRANCH_ELEMENT[branch])


def _chart_hash(year: Pillar, month: Pillar, day: Pillar, hour: Pillar | None) -> str:
    """Return the canonical SHA-256 hex digest for a chart's pillars.

    The hash payload includes :data:`ENGINE_VERSION` so a change to the
    engine forces a new hash even when the four pillars happen to match
    the previous engine's output — protecting the chart cache from stale
    interpretations.
    """

    payload = {
        "engine_version": ENGINE_VERSION,
        "year": year.to_dict(),
        "month": month.to_dict(),
        "day": day.to_dict(),
        "hour": hour.to_dict() if hour else None,
    }
    canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def compute_chart(
    birth_dt_kst: datetime,
    *,
    is_lunar: bool,
    gender: str,
    time_unknown: bool,
) -> SajuChart:
    """Compute the 4-pillar 명식 for the given birth input.

    Args:
        birth_dt_kst: Birth datetime in Korea Standard Time. The function
            ignores timezone information beyond the wall-clock components
            so callers may pass naive or aware datetimes interchangeably.
        is_lunar: When ``True``, treat ``birth_dt_kst`` as a lunar date
            and convert to solar via :func:`lunar_to_solar` first.
        gender: ``"male"`` or ``"female"``. Reserved for future 대운
            (10-year cycle) computation; does not affect the chart itself.
        time_unknown: When ``True``, the hour pillar is omitted and the
            returned :class:`SajuChart` carries ``hour=None``.

    Returns:
        A :class:`SajuChart` whose ``chart_hash`` is byte-identical across
        repeated calls with the same inputs (NFR-017).
    """

    # `gender` is reserved for future 대운 (luck-cycle) calculations.
    # Ignored here; suppress the unused-variable lint.
    del gender

    if is_lunar:
        solar_date = lunar_to_solar(
            birth_dt_kst.year, birth_dt_kst.month, birth_dt_kst.day
        )
    else:
        solar_date = date(birth_dt_kst.year, birth_dt_kst.month, birth_dt_kst.day)

    year_pillar = _year_pillar(solar_date.year)
    month_pillar = _month_pillar(year_pillar, solar_date.month)
    day_pillar = _day_pillar(solar_date)
    hour_pillar = None if time_unknown else _hour_pillar(day_pillar, birth_dt_kst.hour)

    chart_hash = _chart_hash(year_pillar, month_pillar, day_pillar, hour_pillar)

    return SajuChart(
        year=year_pillar,
        month=month_pillar,
        day=day_pillar,
        hour=hour_pillar,
        chart_hash=chart_hash,
        engine_version=ENGINE_VERSION,
    )
