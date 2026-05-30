"""FastAPI router for ``GET /api/v1/me`` (ISSUE-040).

Architecture-Ref: §6.1 ("user_id, profile?, runtime_caps,
has_subscription, has_free_token").
PRD-Ref: FR-006, FR-014, FR-022 (entitlement-driven paywall).

This endpoint is the **real-fetch replacement** for the M1 stub at
``web/src/lib/api/me-stub.ts`` (ISSUE-030). The stub stays in place for
the next iteration so the frontend migration can land in a follow-up
PR — but this endpoint must produce a contract that the stub's call
sites can switch to without breaking.

Response shape (Phase 1 — entitlement is the only required field):

```json
{
  "user_id": "uuid-or-null",
  "entitlement": {
    "kind": "free_token" | "subscription" | "none",
    "token_id": "...",
    "subscription_id": "...",
    "has_anything": bool,
    "requires_payment": bool
  }
}
```

We intentionally keep the surface narrow — ``profile`` and
``runtime_caps`` from architecture §6.1 land in later issues as the
frontend needs them.

Anonymous callers (no session cookie) get ``user_id=null`` and the
``"none"`` entitlement shape. This is a deliberate design choice: the
frontend's paywall page renders the same UI in either case, and
returning 200-with-none lets the same component handle both "logged out"
and "logged in but no entitlement" without branching on status code.
"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from voicesaju.db.engine import get_session
from voicesaju.entitlement.service import (
    EntitlementResult,
    check_entitlement,
)

router = APIRouter(prefix="/api/v1", tags=["me"])


# ---------------------------------------------------------------------------
# Dependencies
# ---------------------------------------------------------------------------


def _get_optional_user_id(request: Request) -> str | None:
    """Return the authenticated user's id, or ``None`` if anonymous.

    Unlike the other ``_get_current_user_id`` hooks (which 401 on
    anonymous), ``GET /api/v1/me`` is **safe to call without a session**
    — the frontend's paywall page hits it on every render. Returning
    ``None`` lets the route handler synthesize the non-member shape
    instead of raising.
    """
    user = getattr(request.state, "user", None)
    if user is None:
        return None
    return user.user_id


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


# Public-facing entitlement summary. Maps EntitlementResult into a
# slightly flatter shape with a stable ``kind`` discriminator so the
# frontend can switch on a single string rather than a tuple of bools.
# Architecture §6.1 calls this out as the canonical paywall input.
class EntitlementSummary(BaseModel):
    kind: Literal["free_token", "subscription", "none"]
    token_id: str | None = None
    subscription_id: str | None = None
    has_anything: bool
    requires_payment: bool


class MeResponse(BaseModel):
    """Body of ``GET /api/v1/me``."""

    user_id: str | None
    entitlement: EntitlementSummary


# ---------------------------------------------------------------------------
# Route
# ---------------------------------------------------------------------------


def _summarise(result: EntitlementResult) -> EntitlementSummary:
    """Project ``EntitlementResult`` into the public ``EntitlementSummary``.

    The internal ``EntitlementResult.preferred_kind`` is the single
    source of truth for which paywall mode the frontend should render —
    by mirroring that field into the public ``kind`` we keep the
    consumption-preference logic in one place (the service) rather than
    duplicating it at every call site.
    """
    return EntitlementSummary(
        kind=result.preferred_kind,
        token_id=result.token_id,
        subscription_id=result.subscription_id,
        has_anything=result.has_anything,
        requires_payment=result.requires_payment,
    )


@router.get(
    "/me",
    response_model=MeResponse,
)
async def get_me(
    user_id: str | None = Depends(_get_optional_user_id),
    db_session: AsyncSession = Depends(get_session),  # noqa: B008
) -> MeResponse:
    """Return ``{user_id, entitlement}`` for the caller.

    Anonymous callers see ``user_id=None`` and an empty entitlement;
    signed-in callers see their resolved id + a summary computed via
    :func:`voicesaju.entitlement.service.check_entitlement`.
    """
    if user_id is None:
        # Anonymous: synthesize the "none" entitlement without hitting
        # the DB (we have no caller identity to query against).
        return MeResponse(
            user_id=None,
            entitlement=EntitlementSummary(
                kind="none",
                has_anything=False,
                requires_payment=True,
            ),
        )

    result = await check_entitlement(
        session=db_session,
        user_id=user_id,
        kind="reading",
    )
    return MeResponse(user_id=user_id, entitlement=_summarise(result))


__all__ = ["router"]
