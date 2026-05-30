"""FastAPI router for the Toss Payments webhook (ISSUE-045).

``POST /api/v1/payments/webhook`` is the inbound Toss → us callback. Toss
signs every body with ``HMAC-SHA256(body, TOSS_WEBHOOK_SECRET)`` and ships
the hex digest in ``X-Toss-Signature``. We:

1. Read the raw body (signature is over bytes, not the parsed JSON).
2. Verify the signature in constant time — fail → 401 with no DB writes.
3. Decode the JSON envelope, dispatch on ``eventType``:
   - ``PAYMENT_DONE``     → flip Payment.status='paid', set paid_at, stamp
                            ``toss_payment_key`` for idempotency.
   - ``PAYMENT_FAILED``   → flip Payment.status='failed'.
   - ``SUBSCRIPTION_RENEWED``  → advance Subscription period + reset
                                 ``monthly_saju_remaining=1``.
   - ``SUBSCRIPTION_CANCELED`` → set ``canceled_at`` + status flag.
   - ``BILLING_FAILED``   → mark Subscription.status='past_due' so the
                            paywall can prompt the user to update their
                            payment method.
4. Always return ``{"status":"ok"}`` once the signature passes — Toss
   retries on non-2xx so we don't want a transient "row not found" to
   queue retries indefinitely.

Idempotency:
- Payment-event handlers key off ``toss_payment_key``. If the row's
  ``toss_payment_key`` already matches the incoming key we return 200
  without re-applying state changes (AC3).
- Subscription handlers compare incoming ``currentPeriodEnd`` to the row
  and only advance forward.

Architecture-Ref: §6.5, §11.4 (A08).
PRD-Ref: FR-021, FR-022.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from voicesaju.config import Settings, get_settings
from voicesaju.db.engine import get_session
from voicesaju.db.models.payments import Payment
from voicesaju.db.models.subscriptions import Subscription
from voicesaju.payment.webhook_signature import verify_signature

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/payments", tags=["payments"])


# ---------------------------------------------------------------------------
# Dependencies (overridable in tests)
# ---------------------------------------------------------------------------


def _get_settings() -> Settings:
    return get_settings()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse_iso(value: str | None) -> datetime | None:
    """Tolerant ISO-8601 parser — Toss uses RFC-3339-with-offset variants."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        # Last-resort: drop a trailing 'Z' (Python <3.11 ISO bug surface).
        if value.endswith("Z"):
            try:
                return datetime.fromisoformat(value[:-1] + "+00:00")
            except ValueError:
                return None
        return None


# ---------------------------------------------------------------------------
# Event handlers — each is responsible for its slice of the DB and never
# raises HTTPException (we ack-and-log on row-not-found to avoid retries
# storming us).
# ---------------------------------------------------------------------------


async def _handle_payment_done(*, data: dict[str, Any], session: AsyncSession) -> None:
    order_id = data.get("orderId")
    payment_key = data.get("paymentKey")
    if not order_id or not payment_key:
        logger.warning(
            "webhook.payment_done missing fields order_id=%s payment_key=%s",
            order_id,
            payment_key,
        )
        return

    payment = (
        await session.execute(select(Payment).where(Payment.toss_order_id == order_id))
    ).scalar_one_or_none()
    if payment is None:
        logger.info("webhook.payment_done unknown order_id=%s", order_id)
        return

    # Idempotency: already-applied → no-op (AC3).
    if payment.toss_payment_key == payment_key and payment.status == "paid":
        return

    payment.status = "paid"
    payment.toss_payment_key = payment_key
    approved_at = _parse_iso(data.get("approvedAt"))
    payment.paid_at = approved_at or datetime.now(tz=UTC)
    await session.commit()


async def _handle_payment_failed(
    *, data: dict[str, Any], session: AsyncSession
) -> None:
    order_id = data.get("orderId")
    payment_key = data.get("paymentKey")
    if not order_id:
        return

    payment = (
        await session.execute(select(Payment).where(Payment.toss_order_id == order_id))
    ).scalar_one_or_none()
    if payment is None:
        logger.info("webhook.payment_failed unknown order_id=%s", order_id)
        return

    # Idempotency: same failed key applied twice → no-op.
    if payment.status == "failed" and payment.toss_payment_key == payment_key:
        return

    payment.status = "failed"
    if payment_key:
        payment.toss_payment_key = payment_key
    await session.commit()


async def _handle_subscription_renewed(
    *, data: dict[str, Any], session: AsyncSession
) -> None:
    user_id = data.get("userId")
    if not user_id:
        return

    sub = (
        await session.execute(
            select(Subscription)
            .where(Subscription.user_id == user_id)
            .where(Subscription.status.in_(("active", "past_due")))
        )
    ).scalar_one_or_none()
    if sub is None:
        logger.info("webhook.subscription_renewed unknown user_id=%s", user_id)
        return

    new_start = _parse_iso(data.get("currentPeriodStart"))
    new_end = _parse_iso(data.get("currentPeriodEnd"))
    if new_end is None:
        logger.warning(
            "webhook.subscription_renewed missing currentPeriodEnd user_id=%s",
            user_id,
        )
        return

    # Only advance forward (idempotent: replaying the same event is a no-op).
    # SQLite (aiosqlite) returns timezone-naive datetimes for
    # ``DateTime(timezone=True)`` columns, so normalise both sides to UTC
    # before comparing.
    stored_end = sub.current_period_end
    if stored_end.tzinfo is None:
        stored_end = stored_end.replace(tzinfo=UTC)
    if new_end <= stored_end:
        return

    if new_start is not None:
        sub.current_period_start = new_start
    sub.current_period_end = new_end
    sub.monthly_saju_remaining = 1
    sub.status = "active"
    await session.commit()


async def _handle_subscription_canceled(
    *, data: dict[str, Any], session: AsyncSession
) -> None:
    user_id = data.get("userId")
    if not user_id:
        return

    sub = (
        await session.execute(
            select(Subscription).where(Subscription.user_id == user_id)
        )
    ).scalar_one_or_none()
    if sub is None:
        logger.info("webhook.subscription_canceled unknown user_id=%s", user_id)
        return

    canceled_at = _parse_iso(data.get("canceledAt")) or datetime.now(tz=UTC)
    # Idempotent: already-canceled → just refresh timestamp if missing.
    if sub.canceled_at is None:
        sub.canceled_at = canceled_at
    if sub.status not in {"canceled", "cancel_at_period_end"}:
        # Until period_end the user keeps access — cancel-at-period-end is
        # the right interim status; a follow-up webhook (or scheduled job)
        # flips to 'canceled' once the period ends.
        sub.status = "cancel_at_period_end"
    await session.commit()


async def _handle_billing_failed(
    *, data: dict[str, Any], session: AsyncSession
) -> None:
    user_id = data.get("userId")
    if not user_id:
        return

    sub = (
        await session.execute(
            select(Subscription)
            .where(Subscription.user_id == user_id)
            .where(Subscription.status == "active")
        )
    ).scalar_one_or_none()
    if sub is None:
        logger.info("webhook.billing_failed unknown user_id=%s", user_id)
        return

    sub.status = "past_due"
    await session.commit()


_HANDLERS = {
    "PAYMENT_DONE": _handle_payment_done,
    "PAYMENT_FAILED": _handle_payment_failed,
    "SUBSCRIPTION_RENEWED": _handle_subscription_renewed,
    "SUBSCRIPTION_CANCELED": _handle_subscription_canceled,
    "BILLING_FAILED": _handle_billing_failed,
}


# ---------------------------------------------------------------------------
# Route
# ---------------------------------------------------------------------------


@router.post(
    "/webhook",
    status_code=status.HTTP_200_OK,
)
async def toss_webhook(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(_get_settings)],
) -> dict[str, str]:
    """Verify HMAC, dispatch by ``eventType``, return ``{"status":"ok"}``.

    AC:
    - valid signature + ``PAYMENT_DONE`` → row flipped to paid (AC1);
    - bad signature → 401, no DB writes (AC2);
    - duplicate delivery on same ``toss_payment_key`` → idempotent (AC3);
    - ``SUBSCRIPTION_RENEWED`` → period advanced + monthly_saju_remaining=1
      (AC4).
    """
    body = await request.body()
    provided_sig = request.headers.get("X-Toss-Signature") or request.headers.get(
        "x-toss-signature", ""
    )
    secret = settings.toss_webhook_secret or ""

    if not verify_signature(body=body, signature=provided_sig, secret=secret):
        # 401 per AC2. The hostile path never reaches the handlers, so no
        # DB writes happen by construction.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": {
                    "code": "invalid_signature",
                    "message": "webhook signature did not verify",
                }
            },
        )

    try:
        envelope = json.loads(body.decode("utf-8")) if body else {}
    except (ValueError, UnicodeDecodeError) as exc:
        logger.warning("webhook json decode failed: %s", exc)
        # Signature checked out — bad JSON is a Toss-side bug. Ack and
        # log to avoid a retry storm; alerting picks this up via the
        # warning log path.
        return {"status": "ok"}

    event_type = envelope.get("eventType")
    data = envelope.get("data") or {}

    handler = _HANDLERS.get(event_type or "")
    if handler is None:
        logger.info("webhook unknown event_type=%s", event_type)
        # Lenient ack so Toss doesn't retry on a future event type.
        return {"status": "ok"}

    await handler(data=data, session=session)
    return {"status": "ok"}


__all__ = [
    "_get_settings",
    "router",
]
