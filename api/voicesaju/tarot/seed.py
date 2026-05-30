"""Deterministic daily-tarot card derivation (ISSUE-047 / FR-013).

The product contract: *given the same KST date and subject (user_id for
members, device_id for non-members), today's Major Arcana card is the
same on every call from every device the user owns*. This is **how the
user trusts the daily ritual** — flipping the same card on phone and
desktop, comparing today's draw with a friend, etc.

The architecture pins a pure SHA256 derivation (§10) — no DB lookup, no
Redis cache for correctness (Redis is a perf-only sidecar; if it's
down, the seed function still returns the same answer):

.. code-block:: python

    seed = f"{today_kst.isoformat()}|{subject_id}"
    digest = hashlib.sha256(seed.encode("utf-8")).digest()
    n = int.from_bytes(digest[:8], "big")
    return n % TOTAL_CARDS

Why SHA256 + first 8 bytes:

- **Uniformity** — SHA256 is cryptographically uniform on any input
  distribution we'll see. ``int.from_bytes(digest[:8], "big")`` gives us
  64 bits of entropy → far more than the 22 buckets need.
- **Modulo bias** — with a 64-bit input and a 22-card modulus, the bias
  is ``2^64 / 22 ≈ 8.4e17`` per bucket: 21 buckets get
  ``floor(2^64/22) + 1`` representatives and one gets ``floor(2^64/22)``
  — a relative skew of ``1 / 8.4e17`` per bucket. Statistically zero.
- **Stability** — SHA256 is not going anywhere. If we ever need to
  re-tune (different bucket count, salted hash for tenant isolation),
  this module is the single switch point.

What this module deliberately does NOT do:

- It does NOT enforce the FR-014 weekly quota — that's a separate
  service (``voicesaju.tarot.quota``). A user whose quota is exhausted
  still sees the *same* card preview behind the paywall.
- It does NOT compute KST. Callers pass an already-localised ``date``
  object; the architecture says ``today_kst`` is derived server-side via
  ``datetime.now(ZoneInfo("Asia/Seoul")).date()`` *before* calling here.
  Keeping the function pure (no implicit clock dependency) makes it
  trivially testable.
- It does NOT validate ``subject_id`` shape — the caller has already
  resolved the right id (user_id vs device_id) via the auth middleware.
  Passing an empty string is permitted (it'll produce a stable bucket
  for "unidentified"); the caller is responsible for whatever policy
  decision happens upstream.

PRD-Ref: FR-013 (deterministic daily card).
Architecture-Ref: §10 (algorithm pin), §6.4 (call site).
data_model-Ref: ``tarot_cards.card_index`` is the natural key the
returned index maps to.
"""

from __future__ import annotations

import hashlib
from datetime import date

# Major Arcana — 22 cards, indices 0..21. Matches the seed in
# ``tarot_cards`` (data_model §4.17 / ISSUE-016). If we ever expand to
# Minor Arcana, this constant — and the chi-squared test in
# ``tests/unit/tarot/test_seed.py`` — moves together.
TOTAL_CARDS: int = 22


def daily_card_index(today_kst: date, subject_id: str) -> int:
    """Return the Major Arcana index (0..21) for *today_kst* + *subject_id*.

    Args:
        today_kst: KST calendar date. The caller is responsible for
            resolving this from ``datetime.now(ZoneInfo("Asia/Seoul"))``
            — passing a UTC ``date`` will *silently* shift the boundary
            by 9 hours, which is precisely the FR-013 bug we want to
            avoid. Keep that resolution at the router edge.
        subject_id: Stable identifier for the caller. Use ``user_id``
            for signed-in users (architecture §6.4 ``vs_sess`` path) or
            ``device_id`` for non-member trials (architecture §11.1
            ``vs_did`` path). The two ID spaces are disjoint by
            construction (uuidv7 for both), so collisions are
            astronomically unlikely.

    Returns:
        An integer ``i`` with ``0 <= i < TOTAL_CARDS``. The value is
        deterministic on (today_kst, subject_id) — the same arguments
        will always produce the same card.

    Notes:
        - Pure function. No DB, no Redis, no clock side effects.
        - Safe under arbitrary concurrency.
        - Idempotent across the test/dev/prod environments — the
          derivation depends only on the two arguments.
    """
    seed = f"{today_kst.isoformat()}|{subject_id}"
    digest = hashlib.sha256(seed.encode("utf-8")).digest()
    # First 8 bytes → 64-bit unsigned int. Plenty of entropy for a
    # 22-bucket modulus; bias is statistically zero (see module
    # docstring). Big-endian is the conventional byte order for
    # cryptographic digests.
    n = int.from_bytes(digest[:8], "big")
    return n % TOTAL_CARDS


__all__ = [
    "TOTAL_CARDS",
    "daily_card_index",
]
