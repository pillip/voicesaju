"""Entitlement check service (ISSUE-040).

Public API:

- :class:`EntitlementResult` — structured response describing which
  entitlements (free token / subscription credit) the caller can use.
- :func:`check_entitlement` — async function returning the result for a
  given (user_id or device_id, kind) pair.

PRD-Ref: FR-006, FR-014, FR-022.
data_model-Ref: AP-16, AP-17, AP-20, AP-21.
architecture-Ref: §6.4 (paywall lookup pattern).
"""

from __future__ import annotations

from voicesaju.entitlement.service import (
    EntitlementKind,
    EntitlementResult,
    check_entitlement,
)

__all__ = [
    "EntitlementKind",
    "EntitlementResult",
    "check_entitlement",
]
