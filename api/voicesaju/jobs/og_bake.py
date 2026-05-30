"""``og_bake`` job stub (ISSUE-057 placeholder, ISSUE-058 real impl).

ISSUE-057 (quote_card row creation) needs the dispatch name
``og_bake`` to be registered on :mod:`voicesaju.jobs.worker` so the
session-end enqueue doesn't raise ``KeyError`` before the real bake
worker lands.

This file ships:

- A no-op coroutine named ``og_bake`` that records the inbound
  ``quote_card_id`` and returns ``None``. It does NOT touch the DB or
  storage — the Phase-1 caller's only invariant is "the queue
  accepts the dispatch name".
- ISSUE-058 will overwrite this module with the real Pillow-based
  compositor that:
    1. Reads the ``quote_cards`` row by id.
    2. Composites a 1080×1920 PNG per the category background colour
       (A-06) + persona text + watermark.
    3. Uploads to ``og/{quote_card_id}.png`` via R2.
    4. Updates ``og_status='baked'`` + ``og_r2_key``.

Keeping the placeholder explicit (rather than a lambda inlined in
``worker.py``) means:

- The registry entry survives across the ISSUE-057 → ISSUE-058 swap
  via a single ``from voicesaju.jobs.og_bake import og_bake`` import.
- Reviewers and grep-driven readers can find "what does the bake do
  in Phase-1" with one ``rg og_bake``.

PRD-Ref: FR-018, FR-020. Architecture-Ref: §8.4.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


async def og_bake(quote_card_id: str, **_unused: Any) -> None:
    """Phase-1 no-op stub for the OG image bake job.

    Args:
        quote_card_id: Id of the ``quote_cards`` row that needs an OG
            image. Logged at INFO so the smoke test in
            ``tests/integration/jobs/test_worker_smoke.py`` can prove
            the dispatch happened.
        **_unused: Forward-compat sink for any future kwargs the
            ISSUE-057 caller might want to thread through.

    Returns:
        Always ``None`` — the row already has ``og_status='pending'``
        from the row-create path and we leave it alone until
        ISSUE-058's real worker overwrites the column.
    """
    logger.info(
        "og_bake (Phase-1 stub): received quote_card_id=%s; "
        "real bake lands in ISSUE-058",
        quote_card_id,
    )
    return None


__all__ = ["og_bake"]
