"""Saju (사주) calculation engine.

Pure-function module that turns a birth datetime into a deterministic
4-pillar 명식 (:class:`SajuChart`). See `docs/data_model.md` §4.6 and
`docs/requirements.md` FR-030 / NFR-017.

Module surface:

- :data:`ENGINE_VERSION` — version tag baked into every chart.
- :func:`compute_chart` — main entry point.
- :class:`SajuChart`, :class:`Pillar`, :class:`Stem`, :class:`Branch`,
  :class:`FiveElements` — value objects exposed by :mod:`voicesaju.saju.models`.
"""

from __future__ import annotations

from voicesaju.saju.engine import ENGINE_VERSION, compute_chart
from voicesaju.saju.models import (
    Branch,
    FiveElements,
    Pillar,
    SajuChart,
    Stem,
)

__all__ = [
    "ENGINE_VERSION",
    "Branch",
    "FiveElements",
    "Pillar",
    "SajuChart",
    "Stem",
    "compute_chart",
]
