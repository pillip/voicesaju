"""FastAPI router for the Toss Payments checkout flow (ISSUE-044).

Two endpoints:

* ``POST /api/v1/payments/checkout`` — creates a pending ``Payment``
  row + returns the Toss redirect targets. Honours ``Idempotency-Key``
  so duplicate POSTs return the existing pending payment.
* ``POST /api/v1/payments/confirm`` — Toss redirect endpoint. Verifies
  the amount + status against the (mocked in Phase-1) Toss confirm
  API and flips the row to ``status='paid'``.

Phase-1 wiring delegates to :class:`MockTossClient` under the default
``PAYMENT_PROVIDER=mock`` setting; ISSUE-043 swaps in
:class:`TossHTTPClient` once real merchant access lands.

Architecture-Ref: §6.5 (payment flow), §11.5 (fraud guard).
PRD-Ref: FR-021 (Toss checkout), US-09 (single payment), US-10
(subscription).
"""

from __future__ import annotations

import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from voicesaju.config import Settings, get_settings
from voicesaju.db.engine import get_session
from voicesaju.db.models.payments import Payment
from voicesaju.payment.toss_client import TossClient, get_toss_client

router = APIRouter(prefix="/api/v1/payments", tags=["payments"])


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


def _get_toss_client(
    settings: Annotated[Settings, Depends(_get_settings)],
) -> TossClient:
    """Build a :class:`TossClient` from settings — tests override this."""
    return get_toss_client(settings=settings)


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class _CheckoutRequest(BaseModel):
    kind: Literal["single", "subscription"]
    method: Literal["tosspay", "kakaopay"] = "tosspay"


class _CheckoutResponse(BaseModel):
    toss_order_id: str
    amount_krw: int
    success_url: str
    fail_url: str


class _ConfirmRequest(BaseModel):
    toss_order_id: str = Field(..., min_length=1)
    payment_key: str = Field(..., min_length=1)
    amount_krw: int = Field(..., gt=0)


class _ConfirmResponse(BaseModel):
    payment_id: str
    status: Literal["paid"]
    amount_krw: int


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.post(
    "/checkout",
    status_code=status.HTTP_201_CREATED,
    response_model=_CheckoutResponse,
)
async def checkout(
    body: _CheckoutRequest,
    request: Request,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
    user_id: Annotated[str, Depends(_get_current_user_id)] = "",
    session: Annotated[AsyncSession, Depends(get_session)] = ...,  # type: ignore[assignment]
    settings: Annotated[Settings, Depends(_get_settings)] = ...,  # type: ignore[assignment]
) -> _CheckoutResponse:
    """Create a pending Payment + return Toss redirect URLs.

    Idempotency: ``Idempotency-Key`` matched against existing
    ``(user_id, idempotency_key)`` returns the same pending row.
    """
    # Idempotent path — return existing pending row first.
    if idempotency_key:
        existing = (
            await session.execute(
                select(Payment).where(
                    Payment.user_id == user_id,
                    Payment.idempotency_key == idempotency_key,
                )
            )
        ).scalar_one_or_none()
        if existing is not None:
            return _build_checkout_response(request, existing, settings)

    amount_krw = (
        settings.price_single_krw
        if body.kind == "single"
        else settings.price_subscription_krw
    )
    toss_order_id = str(uuid.uuid4())

    payment = Payment(
        user_id=user_id,
        kind=body.kind,
        amount_krw=amount_krw,
        method=body.method,
        status="pending",
        toss_order_id=toss_order_id,
        idempotency_key=idempotency_key,
    )
    session.add(payment)
    await session.commit()
    await session.refresh(payment)

    return _build_checkout_response(request, payment, settings)


def _build_checkout_response(
    request: Request, payment: Payment, settings: Settings
) -> _CheckoutResponse:
    """Compose the 201 envelope with the configured (or default) URLs."""
    base = str(request.base_url).rstrip("/")
    success_url = settings.toss_success_url or f"{base}/payment/success"
    fail_url = settings.toss_fail_url or f"{base}/payment/fail"
    return _CheckoutResponse(
        toss_order_id=payment.toss_order_id or "",
        amount_krw=payment.amount_krw,
        success_url=success_url,
        fail_url=fail_url,
    )


@router.post(
    "/confirm",
    status_code=status.HTTP_200_OK,
    response_model=_ConfirmResponse,
)
async def confirm(
    body: _ConfirmRequest,
    user_id: Annotated[str, Depends(_get_current_user_id)] = "",
    session: Annotated[AsyncSession, Depends(get_session)] = ...,  # type: ignore[assignment]
    toss: Annotated[TossClient, Depends(_get_toss_client)] = ...,  # type: ignore[assignment]
) -> _ConfirmResponse:
    """Finalise a payment from a Toss redirect.

    Verifies the upstream status + amount, then flips the row to
    ``status='paid'`` and sets ``paid_at``. The fraud guard returns
    400 when the supplied amount does not match the stored row
    (Architecture §11.5).
    """
    payment = (
        await session.execute(
            select(Payment).where(
                Payment.user_id == user_id,
                Payment.toss_order_id == body.toss_order_id,
            )
        )
    ).scalar_one_or_none()
    if payment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    # Fraud guard — amount must match the row before we even call Toss.
    if body.amount_krw != payment.amount_krw:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": {
                    "code": "amount_mismatch",
                    "message": "confirmed amount does not match pending row",
                }
            },
        )

    # Already finalised — return the existing terminal state.
    if payment.status == "paid":
        return _ConfirmResponse(
            payment_id=str(payment.id), status="paid", amount_krw=payment.amount_krw
        )

    confirmation = await toss.confirm_payment(
        order_id=body.toss_order_id,
        payment_key=body.payment_key,
        amount_krw=body.amount_krw,
    )

    if confirmation.status != "DONE" or confirmation.amount_krw != payment.amount_krw:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": {
                    "code": "toss_confirm_failed",
                    "message": f"upstream status={confirmation.status}",
                }
            },
        )

    payment.status = "paid"
    if confirmation.paid_at is not None:
        from datetime import datetime

        payment.paid_at = datetime.fromisoformat(confirmation.paid_at)
    else:
        from datetime import UTC, datetime

        payment.paid_at = datetime.now(tz=UTC)
    await session.commit()

    return _ConfirmResponse(
        payment_id=str(payment.id), status="paid", amount_krw=payment.amount_krw
    )


__all__ = [
    "_get_current_user_id",
    "_get_settings",
    "_get_toss_client",
    "router",
]
