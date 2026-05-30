"""HMAC-SHA256 signature helpers for Toss Payments webhooks (ISSUE-045).

The webhook handler verifies that each incoming POST originated from Toss
by recomputing ``HMAC-SHA256(body, TOSS_WEBHOOK_SECRET)`` and comparing it
constant-time against the value in the ``X-Toss-Signature`` header.

Why a dedicated helper module:

- Keeps the route thin and testable in isolation (the unit suite hits
  ``verify_signature`` without spinning up FastAPI).
- Centralises the policy decisions that don't belong in the route:
  * empty secrets are always rejected (defence against a half-configured
    deploy that would otherwise validate any signature);
  * the comparison is case-insensitive on the hex digest because Toss
    occasionally returns upper-hex in production responses;
  * non-hex / wrong-length signatures return ``False`` rather than raising
    — the route returns a clean 401 instead of a 500.

Architecture-Ref: §11.4 (A08 — Software & Data Integrity).
PRD-Ref: FR-021, FR-022.
"""

from __future__ import annotations

import hashlib
import hmac

__all__ = [
    "build_signature",
    "verify_signature",
]


def build_signature(body: bytes, secret: str) -> str:
    """Return the lowercase hex digest of ``HMAC-SHA256(body, secret)``.

    The signing direction (used by tests and by the rare case where we
    forward a Toss event verbatim). The production path uses
    :func:`verify_signature` against the incoming request.
    """
    return hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


def verify_signature(*, body: bytes, signature: str, secret: str) -> bool:
    """Constant-time verify that ``signature`` matches the body.

    Returns ``False`` (never raises) for any of:

    - empty ``secret`` — never accept a webhook against a missing key;
    - empty / non-hex / wrong-length ``signature`` — would never have
      come from Toss;
    - HMAC mismatch.

    Accepts the hex digest in either case to match Toss's documented
    behaviour (some endpoints return upper-hex, others lower-hex).
    """
    if not secret:
        # A half-configured deploy must NOT accept arbitrary webhooks.
        # The unit suite exercises this branch explicitly.
        return False
    if not signature:
        return False
    # SHA-256 hex digest is always 64 chars; reject any other length up-front.
    if len(signature) != 64:
        return False
    try:
        # `bytes.fromhex` raises ValueError on non-hex input; that's how we
        # filter out "abcd" and "z" * 64 without resorting to a regex.
        provided = bytes.fromhex(signature)
    except ValueError:
        return False

    expected = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).digest()
    return hmac.compare_digest(expected, provided)
