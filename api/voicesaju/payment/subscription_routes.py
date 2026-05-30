"""FastAPI router for subscription create + cancel (ISSUE-068).

Two endpoints:

* ``POST /api/v1/subscriptions`` — opens a Toss recurring billing handle
  and writes a ``subscriptions`` row with ``status='active'``,
  ``monthly_saju_remaining=1``, and a 30-day period window. Under the
  Phase-1 ``PAYMENT_PROVIDER=mock`` setting we skip the real Toss call
  and just create the local row so the M5 ``/me/billing`` UI has a real
  backend to talk to before ISSUE-043 ships the merchant credentials.

  Idempotency: a user with an existing ``active`` subscription gets
  the same row back (200, not 201). Matches the data_model §4.14
  partial-unique invariant ("one active subscription per user").

* ``POST /api/v1/subscriptions/cancel`` — flips the active row to
  ``status='cancel_at_period_end'``, stamps ``cancel_requested_at=now()``,
  and dispatches the ``subscription_cancel_retry`` arq job so a
  transient Toss outage retries up to 3× without blocking the user.

  Access is preserved until ``current_period_end`` — the
  SUBSCRIPTION_CANCELED webhook (ISSUE-045) flips ``status='canceled'``
  + writes ``canceled_at`` after period end as the terminal step.

PRD-Ref: FR-022, US-12.
Architecture-Ref: §6.5, AP-38, AP-40.
"""

from __future__ import annotations

import contextlib
from datetime import UTC, datetime, timedelta
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from voicesaju.config import Settings, get_settings
from voicesaju.db.engine import get_session
from voicesaju.db.models.subscriptions import Subscription
from voicesaju.jobs.worker import InMemoryQueue, enqueue

router = APIRouter(prefix="/api/v1/subscriptions", tags=["subscriptions"])


# Period length defined as a module constant so the cancel-flow test can
# import it. data_model §4.14 + FR-022: monthly billing cycle.
SUBSCRIPTION_PERIOD: timedelta = timedelta(days=30)


# ---------------------------------------------------------------------------
# Dependencies (overridable in tests)
# ---------------------------------------------------------------------------


def _get_current_user_id(request: Request) -> str:
    """Resolve the caller's ``user_id`` from auth session."""
    user = getattr(request.state, "user", None)
    if user is None or getattr(user, "user_id", None) is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="authentication required",
        )
    return user.user_id


def _get_settings() -> Settings:
    return get_settings()


def _get_cancel_queue() -> InMemoryQueue:
    """Phase-1 queue used to dispatch the cancel-retry job.

    Tests override this via ``app.dependency_overrides`` so the queue
    instance can be inspected for the enqueued payload. Production
    wiring (ISSUE-074) swaps in the arq Redis-backed enqueue helper.
    """
    return InMemoryQueue()


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class _CreateSubscriptionRequest(BaseModel):
    method: Literal["tosspay", "kakaopay"] = "tosspay"


class _SubscriptionResponse(BaseModel):
    id: str
    status: str
    monthly_saju_remaining: int
    current_period_start: datetime
    current_period_end: datetime
    cancel_requested_at: datetime | None = None


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.post(
    "",
    response_model=_SubscriptionResponse,
)
async def create_subscription(
    body: _CreateSubscriptionRequest,
    response: Response,
    user_id: Annotated[str, Depends(_get_current_user_id)],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(_get_settings)],
) -> _SubscriptionResponse:
    """Open a recurring billing handle + write the active row.

    AC1: response carries ``status='active'``, ``monthly_saju_remaining=1``
    and a 30-day period window.

    Idempotent: if the user already has an ``active`` subscription the
    existing row is returned with a 200 (the body type is unchanged so
    the OpenAPI surface stays stable). A row in any other status
    (``cancel_at_period_end``, ``past_due``, ``canceled``) is **not**
    reused — the user must wait for the terminal cancel webhook to
    settle before re-subscribing, matching the data_model §4.14 partial
    unique invariant.
    """
    # ---- Idempotency: reuse an existing active row -----------------------
    existing = (
        await session.execute(
            select(Subscription)
            .where(Subscription.user_id == user_id)
            .where(Subscription.status == "active")
        )
    ).scalar_one_or_none()
    if existing is not None:
        # 200 OK — same row, no new resource created. The route still
        # returns the canonical SubscriptionResponse so the FE never
        # has to handle two shapes.
        response.status_code = status.HTTP_200_OK
        return _to_response(existing)

    # ---- Phase-1: mock provider skips the real Toss call ------------------
    # ISSUE-043 swaps this for a `TossHTTPClient.create_billing_key`
    # call. Until then we treat PAYMENT_PROVIDER=mock as "always
    # succeeds" so the FE can render the success UI end-to-end.
    if settings.payment_provider.lower() != "mock":
        # Phase-2 path: dispatch the real Toss call. Documented but not
        # implemented here so the merchant credentials never accidentally
        # leak into M5; a follow-up issue lands the real wiring.
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error": {
                    "code": "payment_provider_not_available",
                    "message": "real Toss subscription wiring lands with ISSUE-043",
                }
            },
        )

    now = datetime.now(tz=UTC)
    sub = Subscription(
        user_id=user_id,
        status="active",
        monthly_saju_remaining=1,
        current_period_start=now,
        current_period_end=now + SUBSCRIPTION_PERIOD,
    )
    session.add(sub)
    await session.commit()
    await session.refresh(sub)

    response.status_code = status.HTTP_201_CREATED
    return _to_response(sub)


@router.post(
    "/cancel",
    response_model=_SubscriptionResponse,
)
async def cancel_subscription(
    user_id: Annotated[str, Depends(_get_current_user_id)],
    session: Annotated[AsyncSession, Depends(get_session)],
    queue: Annotated[InMemoryQueue, Depends(_get_cancel_queue)],
) -> _SubscriptionResponse:
    """Schedule cancel at period end + dispatch the retry job.

    AC2: status → ``cancel_at_period_end``, ``cancel_requested_at=now()``.
    Access is preserved until ``current_period_end`` — we do NOT clear
    the period fields here. The SUBSCRIPTION_CANCELED webhook (ISSUE-045)
    is the canonical terminal-state writer.

    AC3: a transient Toss outage is handled by the arq
    ``subscription_cancel_retry`` job which retries up to 3× via tenacity.
    Enqueueing happens after the local row is updated so the user's
    in-app state already reflects the cancel intent regardless of
    upstream reachability.
    """
    sub = (
        await session.execute(
            select(Subscription)
            .where(Subscription.user_id == user_id)
            .where(Subscription.status == "active")
        )
    ).scalar_one_or_none()
    if sub is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": {
                    "code": "no_active_subscription",
                    "message": "no active subscription to cancel",
                }
            },
        )

    sub.status = "cancel_at_period_end"
    sub.cancel_requested_at = datetime.now(tz=UTC)
    await session.commit()
    await session.refresh(sub)

    # Dispatch the retry job — failures inside the job don't roll back
    # the local row (we want the user to see cancel-at-period-end
    # immediately; the SUBSCRIPTION_CANCELED webhook is the source of
    # truth for the terminal state). ``contextlib.suppress`` keeps the
    # defensive guard concise: the registry is populated at import time,
    # so KeyError here means a deploy-side wiring bug — we log via the
    # worker, never via a 500 to the user.
    with contextlib.suppress(KeyError):
        await enqueue(queue, "subscription_cancel_retry", subscription_id=str(sub.id))

    return _to_response(sub)


def _to_response(sub: Subscription) -> _SubscriptionResponse:
    """Project Subscription ORM row → the public response envelope."""
    return _SubscriptionResponse(
        id=str(sub.id),
        status=sub.status,
        monthly_saju_remaining=sub.monthly_saju_remaining,
        current_period_start=sub.current_period_start,
        current_period_end=sub.current_period_end,
        cancel_requested_at=sub.cancel_requested_at,
    )


__all__ = [
    "SUBSCRIPTION_PERIOD",
    "_get_cancel_queue",
    "_get_current_user_id",
    "_get_settings",
    "_to_response",
    "router",
]
