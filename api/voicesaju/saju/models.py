"""Value-object types used by the Saju engine.

These mirror the domain primitives documented in `docs/data_model.md` §4.6.
The engine is a pure function, so the dataclasses here are frozen and the
enums are :class:`str`-backed (:class:`StrEnum`) — this guarantees both
hashability and stable JSON serialization across runs (NFR-017 determinism).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class Stem(StrEnum):
    """천간 (Heavenly Stems) — the 10 stems of 60-갑자 (Sexagenary Cycle)."""

    GAP = "갑"
    EUL = "을"
    BYEONG = "병"
    JEONG = "정"
    MU = "무"
    GI = "기"
    GYEONG = "경"
    SIN_STEM = "신"
    IM = "임"
    GYE = "계"


class Branch(StrEnum):
    """지지 (Earthly Branches) — the 12 branches of 60-갑자."""

    JA = "자"
    CHUK = "축"
    IN = "인"
    MYO = "묘"
    JIN = "진"
    SA = "사"
    O_BRANCH = "오"  # noqa: E741 — single-letter `O` would shadow stdlib; suffix retained for clarity
    MI = "미"
    SIN_BRANCH = "신"
    YU = "유"
    SUL = "술"
    HAE = "해"


class FiveElements(StrEnum):
    """오행 — the five elements (wood / fire / earth / metal / water)."""

    WOOD = "木"
    FIRE = "火"
    EARTH = "土"
    METAL = "金"
    WATER = "水"


# Element mappings (천간 → 오행).
# Reference: 갑을=木, 병정=火, 무기=土, 경신=金, 임계=水.
STEM_ELEMENT: dict[Stem, FiveElements] = {
    Stem.GAP: FiveElements.WOOD,
    Stem.EUL: FiveElements.WOOD,
    Stem.BYEONG: FiveElements.FIRE,
    Stem.JEONG: FiveElements.FIRE,
    Stem.MU: FiveElements.EARTH,
    Stem.GI: FiveElements.EARTH,
    Stem.GYEONG: FiveElements.METAL,
    Stem.SIN_STEM: FiveElements.METAL,
    Stem.IM: FiveElements.WATER,
    Stem.GYE: FiveElements.WATER,
}

# Element mappings (지지 → 오행).
# Reference: 인묘=木, 사오=火, 진술축미=土, 신유=金, 자해=水.
BRANCH_ELEMENT: dict[Branch, FiveElements] = {
    Branch.JA: FiveElements.WATER,
    Branch.CHUK: FiveElements.EARTH,
    Branch.IN: FiveElements.WOOD,
    Branch.MYO: FiveElements.WOOD,
    Branch.JIN: FiveElements.EARTH,
    Branch.SA: FiveElements.FIRE,
    Branch.O_BRANCH: FiveElements.FIRE,
    Branch.MI: FiveElements.EARTH,
    Branch.SIN_BRANCH: FiveElements.METAL,
    Branch.YU: FiveElements.METAL,
    Branch.SUL: FiveElements.EARTH,
    Branch.HAE: FiveElements.WATER,
}

# Ordered stems / branches for indexing into the 60-갑자 cycle.
STEMS_ORDER: tuple[Stem, ...] = (
    Stem.GAP,
    Stem.EUL,
    Stem.BYEONG,
    Stem.JEONG,
    Stem.MU,
    Stem.GI,
    Stem.GYEONG,
    Stem.SIN_STEM,
    Stem.IM,
    Stem.GYE,
)
BRANCHES_ORDER: tuple[Branch, ...] = (
    Branch.JA,
    Branch.CHUK,
    Branch.IN,
    Branch.MYO,
    Branch.JIN,
    Branch.SA,
    Branch.O_BRANCH,
    Branch.MI,
    Branch.SIN_BRANCH,
    Branch.YU,
    Branch.SUL,
    Branch.HAE,
)


@dataclass(frozen=True, slots=True)
class Pillar:
    """One of the 4 사주 columns (年/月/日/時)."""

    stem: Stem
    branch: Branch
    element: FiveElements
    ten_god: str | None = None

    def to_dict(self) -> dict[str, str | None]:
        """Canonical dict form used for hashing and JSON serialization."""

        return {
            "stem": str(self.stem),
            "branch": str(self.branch),
            "element": str(self.element),
            "ten_god": self.ten_god,
        }


@dataclass(frozen=True, slots=True)
class SajuChart:
    """4-pillar 명식 produced by :func:`voicesaju.saju.engine.compute_chart`.

    `hour` is :data:`None` when the user did not provide a birth time
    (`time_unknown=True`); 3 pillars are then exposed and the hour slot
    is omitted from the hash payload (deterministic across runs).
    """

    year: Pillar
    month: Pillar
    day: Pillar
    hour: Pillar | None
    chart_hash: str
    engine_version: str

    def to_dict(self) -> dict[str, object]:
        """Canonical dict form used by callers (and the hash function)."""

        return {
            "year": self.year.to_dict(),
            "month": self.month.to_dict(),
            "day": self.day.to_dict(),
            "hour": self.hour.to_dict() if self.hour else None,
            "engine_version": self.engine_version,
        }
