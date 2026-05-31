"""arq-discoverable refund retry job (ISSUE-076, FR-023, FR-033).

When a paid reading enters ``status='failed'`` the pipeline enqueues
``refund_for_reading(reading_id=...)`` against the worker; this module
holds the dispatch wrapper.

The flow:

1. Resolve *reading_id* → its paying ``Payment`` row via the entitlement
   chain (``Reading.entitlement_kind='payment'`` → ``Reading.payment_id``).
2. Hand the payment to :func:`voicesaju.payment.refund.refund_payment`
   with an injected ``toss_refund_call`` so the retry boundary stays
   here (the service code is provider-agnostic).
3. Wrap the Toss call in :mod:`tenacity` so transient HTTP failures get
   retried up to ``MAX_REFUND_ATTEMPTS`` before the fallback path
   (credit a ``failure_compensation`` FreeToken) kicks in. This mirrors
   the ISSUE-068 subscription-cancel retry pattern.

The job is registered against ``_JOB_REGISTRY`` under its own
``__name__`` so both the in-memory queue (Phase-1 tests) and the real
arq Redis worker (Phase-2) can dispatch by name. The integration test
asserts the registration directly via ``_JOB_REGISTRY['refund_for_reading']``.

PRD-Ref: FR-023 (automatic refund), FR-033 (LLM failure UX).
Architecture-Ref: §6.5, AP-41 (refund queue + fallback FreeToken).
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from contextlib import AbstractAsyncContextManager
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from voicesaju.db.models.readings import Reading
from voicesaju.jobs.worker import register
from voicesaju.payment.refund import (
    RefundResult,
    TossRefundError,
    refund_payment,
)

logger = logging.getLogger(__name__)


# Mirrors the AC contract: up to 3 in-job Toss retries before the
# fallback path takes over. Keep this aligned with
# ``MAX_CANCEL_ATTEMPTS`` (ISSUE-068) so ops alerting can use a single
# threshold across the retry jobs.
MAX_REFUND_ATTEMPTS: int = 3


# Session factory protocol — anything that yields an ``AsyncSession`` via
# ``async with`` works. Production wires this to the FastAPI app's
# session-maker; tests pass a lambda that opens a new session per call.
SessionFactory = Callable[[], AbstractAsyncContextManager[AsyncSession]]

# Injected Toss-side refund call. Returns the Toss-side refund id or
# raises :class:`TossRefundError` to trigger the fallback path. Tests
# pass a stub directly; production wires the real ``TossHTTPClient`` /
# ``MockTossClient`` ``refund_payment`` method.
TossRefundCall = Callable[..., Awaitable[str]]


async def _resolve_payment_id_from_reading(
    session: AsyncSession,
    reading_id: str,
) -> str:
    """Return the ``payment_id`` linked to *reading_id*.

    Raises ``LookupError`` if the reading row is missing or if its
    ``entitlement_kind`` doesn't point at a payment (e.g. the reading
    was redeemed via a free token or a subscription — those don't refund
    money; ops should hand-process those cases).
    """
    result = await session.execute(select(Reading).where(Reading.id == reading_id))
    reading = result.scalar_one_or_none()
    if reading is None:
        raise LookupError(f"refund_for_reading: no reading row id={reading_id!r}")
    if reading.entitlement_kind != "payment" or reading.payment_id is None:
        raise LookupError(
            f"refund_for_reading: reading id={reading_id!r} has "
            f"entitlement_kind={reading.entitlement_kind!r} and "
            f"payment_id={reading.payment_id!r}; only 'payment' "
            "entitlements are refundable here."
        )
    return str(reading.payment_id)


async def _refund_with_retry(
    *,
    session: AsyncSession,
    payment_id: str,
    reading_id: str | None,
    reason: str,
    toss_refund_call: TossRefundCall,
) -> RefundResult:
    """Invoke :func:`refund_payment` with a tenacity-wrapped Toss call.

    Transient ``RuntimeError`` (e.g. network blips) trigger up to
    ``MAX_REFUND_ATTEMPTS`` retries with exponential backoff. After
    exhaustion the wrapper raises :class:`TossRefundError` so
    :func:`refund_payment` takes the fallback path (FreeToken credit)
    rather than burying the failure.

    We retry **inside** the job (rather than re-enqueueing) so the
    end-to-end refund decision happens within a single AsyncSession
    transaction — matching the ISSUE-068 retry job's invariant.
    """

    async def _retrying_toss_call(*, payment_key: str, amount_krw: int) -> str:
        try:
            async for attempt in AsyncRetrying(
                stop=stop_after_attempt(MAX_REFUND_ATTEMPTS),
                # Tight defaults so tests don't sleep — production
                # operators can override via the arq job config.
                wait=wait_exponential(multiplier=0.001, min=0.001, max=0.01),
                retry=retry_if_exception_type(RuntimeError),
                reraise=True,
            ):
                with attempt:
                    return await toss_refund_call(
                        payment_key=payment_key,
                        amount_krw=amount_krw,
                    )
        except TossRefundError:
            # Already the canonical "go to fallback" signal — let it
            # bubble straight to refund_payment().
            raise
        except RuntimeError as exc:
            # Tenacity exhausted retries on a generic transient error;
            # normalise to TossRefundError so the fallback path runs.
            raise TossRefundError(
                f"refund_retry: exhausted {MAX_REFUND_ATTEMPTS} attempts: {exc}"
            ) from exc
        # Defensive — AsyncRetrying always returns or raises before this point.
        raise TossRefundError(  # pragma: no cover - defensive guard
            "refund_retry: no result from retry loop"
        )

    return await refund_payment(
        session=session,
        payment_id=payment_id,
        reason=reason,  # type: ignore[arg-type]
        toss_refund_call=_retrying_toss_call,
        reading_id=reading_id,
    )


async def refund_for_reading(
    *args: Any,
    reading_id: str,
    session_factory: SessionFactory,
    toss_refund_call: TossRefundCall,
    reason: str = "llm_failure",
    **kwargs: Any,
) -> RefundResult:
    """Resolve *reading_id* → payment, then refund it via the retry wrapper.

    The arq worker dispatches this by name via the ``_JOB_REGISTRY``.
    Production callers (the reading pipeline's failure branch) pass the
    app's session-maker and the active Toss client's ``refund_payment``
    method; tests pass stubs directly.

    *reason* defaults to ``"llm_failure"`` — that's the canonical trigger
    for the automatic refund worker (FR-033 LLM failure UX). Ops manual
    refunds go through a different path and pass ``"manual_ops"``.

    Returns the :class:`RefundResult` from :func:`refund_payment` so the
    caller (or the arq result store) can log the outcome.
    """
    async with session_factory() as session:
        payment_id = await _resolve_payment_id_from_reading(session, reading_id)
        result = await _refund_with_retry(
            session=session,
            payment_id=payment_id,
            reading_id=reading_id,
            reason=reason,
            toss_refund_call=toss_refund_call,
        )
        await session.commit()
        return result


# Register at import time so ``voicesaju.jobs.worker._JOB_REGISTRY``
# picks the job up. The worker module imports this module from its
# population block (see voicesaju/jobs/worker.py).
register(refund_for_reading)


__all__ = [
    "MAX_REFUND_ATTEMPTS",
    "SessionFactory",
    "TossRefundCall",
    "refund_for_reading",
]
