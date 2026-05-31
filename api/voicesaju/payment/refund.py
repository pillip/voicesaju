"""Automatic refund service (ISSUE-076, FR-023, FR-033).

When a paid reading fails — LLM unavailable, TTS outage, etc. — the
pipeline enqueues ``refund_for_reading(reading_id)`` (see
:mod:`voicesaju.jobs.refund_retry`) which in turn calls
:func:`refund_payment` here. The contract:

1. **Happy path** — Toss accepts the refund. We:
   - Set ``payments.status='refunded'`` and bump ``refunded_amount_krw``
     to the full payment amount (v1 only refunds in full).
   - Insert a ``refunds`` row with ``status='succeeded'``,
     ``toss_refund_id`` populated from Toss's response, and
     ``finished_at`` stamped to now.
   - Return :class:`RefundResult` so the caller can log the outcome.

2. **Toss failure path** — the upstream call raises
   :class:`TossRefundError` after retries are exhausted. We:
   - Leave the payment row untouched (we did NOT refund money, so the
     ``status='paid'`` invariant must hold).
   - Insert a ``free_tokens`` row with ``kind='failure_compensation'``
     owned by the paying user. This is the "ticket back" the AC promises.
   - Insert a ``refunds`` row with ``status='failed_credited'`` and
     ``fallback_token_id`` pointing at the freshly minted token, so
     ops can trace which token compensated for which Toss outage.
   - Return :class:`RefundResult` with ``status='failed_credited'``.

We keep the Toss call **injected** so the job wrapper (and tests) can
swap in the real ``TossHTTPClient`` (Phase-2) or a stub (Phase-1 /
tests). The mock client adds a ``refund_payment(...)`` method that
returns a synthetic refund id under ``PAYMENT_PROVIDER=mock``.

PRD-Ref: FR-023 (automatic refund on reading failure), FR-033 (LLM
failure UX).
Architecture-Ref: §6.5 (Payment & subscription flow), AP-41 (refund
queue + fallback FreeToken).
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from voicesaju.db.models.free_tokens import FreeToken
from voicesaju.db.models.payments import Payment
from voicesaju.db.models.refunds import Refund

# Reason strings mirror the data_model §4.15 CHECK constraint —
# ``reason IN ('llm_failure','manual_ops','tts_outage','user_request')``.
RefundReason = Literal["llm_failure", "manual_ops", "tts_outage", "user_request"]


class TossRefundError(RuntimeError):
    """Raised by the injected Toss call when the upstream refund fails.

    Caught by :func:`refund_payment` so the fallback path can mint a
    ``failure_compensation`` FreeToken. The retry job
    (:mod:`voicesaju.jobs.refund_retry`) catches transient errors *before*
    we get here — by the time ``TossRefundError`` lands, retries are
    exhausted and the user has earned a token.
    """


# Type alias for the injected upstream call. Keeping it as a Callable
# (rather than a Protocol) lets tests pass a plain ``async def`` stub
# without a wrapper class.
TossRefundCall = Callable[..., Awaitable[str]]


@dataclass(frozen=True, slots=True)
class RefundResult:
    """Outcome envelope returned by :func:`refund_payment`."""

    payment_id: str
    refund_id: str
    status: Literal["succeeded", "failed_credited"]
    amount_krw: int
    toss_refund_id: str | None
    fallback_token_id: str | None


async def refund_payment(
    *,
    session: AsyncSession,
    payment_id: str,
    reason: RefundReason,
    toss_refund_call: TossRefundCall,
    reading_id: str | None = None,
) -> RefundResult:
    """Refund *payment_id* via *toss_refund_call*; fall back to a FreeToken on failure.

    The caller owns the transaction — we add rows + flush so the IDs are
    available, but the surrounding ``session.commit()`` lives in the
    caller (typically the job wrapper).

    ``toss_refund_call`` is injected so:
    - the job (Phase-2) can wire ``TossHTTPClient.refund_payment(...)``,
    - the job (Phase-1) can wire ``MockTossClient.refund_payment(...)``,
    - tests can pass an ``async def _ok(...)`` or
      ``async def _fail(...)`` stub directly.

    On Toss failure we mint a ``failure_compensation`` FreeToken owned
    by the paying user — that's the "환불 또는 무료 이용권이 지급되었습니다"
    contract the AC3 copy gates on. The frontend (ISSUE-075's
    /error/llm-failed screen) is the surface that actually notifies the
    user; the backend only guarantees the ledger row exists.
    """
    payment = await _load_payment(session, payment_id)
    amount = payment.amount_krw
    now = datetime.now(tz=UTC)

    try:
        toss_refund_id = await toss_refund_call(
            payment_key=payment.toss_payment_key or "",
            amount_krw=amount,
        )
    except TossRefundError:
        # --- Fallback path: mint a failure_compensation FreeToken ------
        token = FreeToken(
            user_id=payment.user_id,
            kind="failure_compensation",
        )
        session.add(token)
        await session.flush()  # populate token.id for the FK link.

        refund = Refund(
            payment_id=payment_id,
            reading_id=reading_id,
            amount_krw=amount,
            reason=reason,
            toss_refund_id=None,
            fallback_token_id=str(token.id),
            status="failed_credited",
            finished_at=now,
        )
        session.add(refund)
        await session.flush()

        return RefundResult(
            payment_id=payment_id,
            refund_id=str(refund.id),
            status="failed_credited",
            amount_krw=amount,
            toss_refund_id=None,
            fallback_token_id=str(token.id),
        )

    # --- Happy path: flip the payment row + log the refund -------------
    payment.status = "refunded"
    payment.refunded_amount_krw = amount

    refund = Refund(
        payment_id=payment_id,
        reading_id=reading_id,
        amount_krw=amount,
        reason=reason,
        toss_refund_id=toss_refund_id,
        fallback_token_id=None,
        status="succeeded",
        finished_at=now,
    )
    session.add(refund)
    await session.flush()

    return RefundResult(
        payment_id=payment_id,
        refund_id=str(refund.id),
        status="succeeded",
        amount_krw=amount,
        toss_refund_id=toss_refund_id,
        fallback_token_id=None,
    )


async def _load_payment(session: AsyncSession, payment_id: str) -> Payment:
    """Fetch the ``Payment`` row; raise if absent."""
    result = await session.execute(select(Payment).where(Payment.id == payment_id))
    payment = result.scalar_one_or_none()
    if payment is None:
        raise LookupError(f"refund_payment: no payment row id={payment_id!r}")
    return payment


__all__ = [
    "RefundReason",
    "RefundResult",
    "TossRefundCall",
    "TossRefundError",
    "refund_payment",
]
