"""WebView origin allowlist guard (ISSUE-046).

Toss WebView delivers our pages via an iframe under
``https://m.tosspayments.com``. To carry a session cookie across that
boundary we need ``SameSite=None; Secure`` cookies — but a relaxed
SameSite attribute is dangerous if any origin can request it. This
module is the policy gate: only origins on the allowlist
(``Settings.toss_webview_origin_allowlist``) qualify for the relaxed
attributes; everything else is rejected by the route with 403.

Architecture-Ref: §11.1 (auth strategy table — Toss WebView row).
PRD-Ref: FR-016, FR-024, US-14.
"""

from __future__ import annotations

from collections.abc import Sequence

__all__ = [
    "is_allowed_webview_origin",
    "normalize_origin",
]


def normalize_origin(raw: str | None) -> str:
    """Return a lowercased, trailing-slash-stripped origin string.

    Empty / None inputs collapse to ``""`` so the caller can simply
    compare to a configured allowlist without surrounding noise.
    """
    if not raw:
        return ""
    return raw.strip().rstrip("/").lower()


def is_allowed_webview_origin(
    origin: str | None,
    *,
    allowlist: Sequence[str],
) -> bool:
    """Return True iff ``origin`` exactly matches an allowlisted entry.

    Policy:

    - Exact match only — subtree matches (``foo.m.tosspayments.com``)
      are rejected.
    - ``https://`` is required — an ``http://`` origin can never receive
      a ``SameSite=None; Secure`` cookie anyway, so we reject up-front
      to surface the misconfiguration loudly.
    - Empty / missing origin → False.
    - Empty allowlist → False (defence against a half-configured deploy
      that would otherwise accept everything).
    """
    normalized = normalize_origin(origin)
    if not normalized:
        return False
    if not normalized.startswith("https://"):
        return False
    if not allowlist:
        return False
    normalized_allowlist = {normalize_origin(entry) for entry in allowlist}
    return normalized in normalized_allowlist
