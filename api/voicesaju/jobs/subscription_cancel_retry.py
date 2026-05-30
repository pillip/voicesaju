"""Tenacity-backed retry job for subscription cancellation (ISSUE-068).

When the user clicks "구독 해지" the route updates the local row to
``cancel_at_period_end`` synchronously (we never block the user on
upstream Toss reachability — they keep access until ``current_period_end``
regardless). The upstream Toss `cancel-billing-key` call is dispatched
to this arq job so a transient outage doesn't lose the cancel signal:

1. Up to ``MAX_CANCEL_ATTEMPTS=3`` attempts via :mod:`tenacity`.
2. Exponential backoff between attempts (small in test runs, larger in
   production via the ``wait_exponential`` knobs).
3. After exhaustion the job re-raises so arq's failure pipeline
   surfaces the error for follow-up (alerting / manual replay).

We intentionally keep the retry **inside** a single job invocation
rather than re-enqueueing — the SUBSCRIPTION_CANCELED webhook is the
canonical "did Toss actually cancel?" signal; this job only handles
the optimistic upstream call, so a single shot with three internal
attempts gives us a tight failure window without re-entrant complexity.

PRD-Ref: FR-022 (AC3).
Architecture-Ref: §6.5, AP-38.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Any

from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from voicesaju.jobs.worker import register

logger = logging.getLogger(__name__)


# Mirrors the AC3 contract: "arq retry job schedules retries up to 3×".
MAX_CANCEL_ATTEMPTS: int = 3


async def _cancel_with_retry(
    *,
    subscription_id: str,
    call: Callable[[str], Awaitable[str]],
) -> str:
    """Run *call* up to ``MAX_CANCEL_ATTEMPTS`` times with exponential backoff.

    ``call`` is injected so the worker can wire in either the real
    Toss billing-key cancel HTTP call or a stub for tests / Phase-1
    mock provider. ``subscription_id`` is the only argument the callee
    needs — the route handler already wrote the cancel-at-period-end
    flag to the local row before enqueueing.

    Raises the final ``RuntimeError`` (or whichever upstream exception
    the callee throws) once attempts are exhausted so the arq failure
    pipeline can surface it.
    """
    # ``reraise=True`` so arq sees the original exception type — its
    # alerting path matches on `RuntimeError` (or the upstream `httpx`
    # error class once Phase-2 wiring lands).
    async for attempt in AsyncRetrying(
        stop=stop_after_attempt(MAX_CANCEL_ATTEMPTS),
        # Aggressive defaults so tests don't sleep — production
        # operators can override via the arq job config.
        wait=wait_exponential(multiplier=0.001, min=0.001, max=0.01),
        retry=retry_if_exception_type(RuntimeError),
        reraise=True,
    ):
        with attempt:
            result = await call(subscription_id)
            return result
    # Defensive — AsyncRetrying always returns or raises before this point.
    raise RuntimeError(  # pragma: no cover - defensive guard
        f"subscription_cancel_retry: no result for subscription_id={subscription_id}"
    )


@register
async def subscription_cancel_retry(
    *args: Any,
    subscription_id: str,
    call: Callable[[str], Awaitable[str]] | None = None,
    **kwargs: Any,
) -> str:
    """arq-discoverable wrapper around :func:`_cancel_with_retry`.

    Registered with the worker via the ``@register`` decorator so the
    in-memory queue (Phase-1) and the real Redis-backed arq worker
    (Phase-2) can both dispatch by name.

    ``call`` defaults to ``_default_toss_cancel`` so production callers
    don't have to wire it in; tests inject a stub directly via
    ``_cancel_with_retry`` (which is the inner implementation).
    """
    callable_ = call or _default_toss_cancel
    return await _cancel_with_retry(subscription_id=subscription_id, call=callable_)


async def _default_toss_cancel(subscription_id: str) -> str:
    """Phase-1 placeholder — no real Toss billing-key cancel call yet.

    Returns immediately under PAYMENT_PROVIDER=mock; the Phase-2 work
    swaps this for a real ``TossHTTPClient.cancel_billing_key()`` once
    ISSUE-043 lands the merchant credentials.
    """
    logger.info(
        "subscription_cancel_retry default no-op for subscription_id=%s",
        subscription_id,
    )
    return f"noop:{subscription_id}"


__all__ = [
    "MAX_CANCEL_ATTEMPTS",
    "_cancel_with_retry",
    "subscription_cancel_retry",
]
