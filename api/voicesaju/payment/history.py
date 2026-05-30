"""FastAPI router for ``GET /api/v1/payments/history`` (ISSUE-073).

Returns the caller's paginated single-purchase history, newest first. The
backing index ``payments_user_created_idx`` (declared in alembic 0006
for ISSUE-014) gives an O(log N) scan on ``(user_id, created_at DESC)``
so the 20-per-page query stays in single-digit milliseconds even with
years of history.

Response shape (one row per element):

```json
{
  "id": "uuid",
  "type": "single" | "subscription",
  "category": null,
  "amount_krw": 4900,
  "status": "pending" | "paid" | "failed" | ...,
  "paid_at": "2026-05-01T10:00:00+00:00" | null,
  "refunded_amount_krw": 0
}
```

Why ``type`` mirrors ``Payment.kind``: the database column is named
``kind`` for backwards compatibility with M1's mock adapter, but the
public API uses ``type`` per FR-026 vocabulary. The mapping happens at
the response-model layer so future column renames don't ripple to the
frontend.

``category`` is a Phase-1 placeholder. Single payments don't have a
saju category column on ``payments`` (the category is associated with
the downstream ``readings`` row); when ISSUE-067's billing UI needs
per-row category, the row will be enriched via a follow-up. For now we
return ``null`` so the response shape is stable.

Architecture-Ref: §6.5 (payment flow), AP-39 (history index).
PRD-Ref: FR-026 (payment history), US-12 (subscription / single).
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from voicesaju.db.engine import get_session
from voicesaju.db.models.payments import Payment

router = APIRouter(prefix="/api/v1/payments", tags=["payments"])


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------


# Page size lives at module scope so tests can patch it without monkeypatching
# the route handler. Issue spec mandates 20.
PAGE_SIZE: int = 20


# ---------------------------------------------------------------------------
# Dependencies (overridable in tests)
# ---------------------------------------------------------------------------


def _get_current_user_id(request: Request) -> str:
    """Resolve the caller's ``user_id`` from auth session.

    Mirrors the helper in ``voicesaju.payment.routes`` — kept as a
    module-local symbol so test fixtures can override the dependency
    without coupling to the checkout router's import surface.
    """
    user = getattr(request.state, "user", None)
    if user is None or getattr(user, "user_id", None) is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="authentication required",
        )
    return user.user_id


# ---------------------------------------------------------------------------
# Response schema
# ---------------------------------------------------------------------------


class PaymentHistoryRow(BaseModel):
    """One row in the ``GET /payments/history`` response (FR-026)."""

    id: str
    # Public vocabulary; mirrors `Payment.kind`. See module docstring.
    type: Literal["single", "subscription"]
    # Placeholder until the saju category is joined in via ISSUE-067.
    category: str | None = None
    amount_krw: int
    status: str
    paid_at: datetime | None = None
    refunded_amount_krw: int


# ---------------------------------------------------------------------------
# Route
# ---------------------------------------------------------------------------


@router.get(
    "/history",
    response_model=list[PaymentHistoryRow],
)
async def list_payment_history(
    user_id: Annotated[str, Depends(_get_current_user_id)],
    session: Annotated[AsyncSession, Depends(get_session)],
    page: Annotated[
        int,
        Query(
            ge=1,
            description="1-indexed page number; 20 rows per page.",
        ),
    ] = 1,
) -> list[PaymentHistoryRow]:
    """Return the caller's payment history, newest first, 20 per page.

    AC1: 25 payments + ``?page=1`` → 20 rows desc by ``created_at``.
    AC2: 0 payments → ``[]``.
    """
    offset = (page - 1) * PAGE_SIZE
    stmt = (
        select(Payment)
        .where(Payment.user_id == user_id)
        .order_by(desc(Payment.created_at))
        .offset(offset)
        .limit(PAGE_SIZE)
    )
    rows = (await session.execute(stmt)).scalars().all()
    return [_row_to_response(p) for p in rows]


def _row_to_response(p: Payment) -> PaymentHistoryRow:
    """Project ORM Payment → public response row.

    Centralised so the type/kind alias and the ``category=None`` Phase-1
    placeholder live in one place — future column moves only touch this
    function.
    """
    # `Payment.kind` is constrained by `payment_type_enum` to
    # {single, subscription} at the DB layer, so the Literal cast is safe.
    return PaymentHistoryRow(
        id=str(p.id),
        type=p.kind,  # type: ignore[arg-type]
        category=None,
        amount_krw=p.amount_krw,
        status=p.status,
        paid_at=p.paid_at,
        refunded_amount_krw=p.refunded_amount_krw,
    )


__all__ = ["PAGE_SIZE", "PaymentHistoryRow", "_get_current_user_id", "router"]
