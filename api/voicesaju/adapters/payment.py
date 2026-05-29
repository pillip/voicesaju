"""Payment adapter Protocol + concrete implementations.

Phase 1 ships the `MockPaymentAdapter`, which produces deterministic
checkout sessions and auto-fires a `succeeded` webhook after a 3-second
delay so the full M2 payment flow runs without a Toss merchant account.
The `TossPaymentAdapter` stub keeps the env switch (`PAYMENT_PROVIDER=toss`)
importable; its methods raise `NotImplementedError` on first call so the
app still boots without credentials.

PRD-Ref: FR-024 (mock adapter), ISSUE-043 (real Toss client, Phase 2).
"""

from __future__ import annotations

import asyncio
import hashlib
from datetime import UTC, datetime
from typing import Literal, Protocol

from pydantic import BaseModel, Field

PaymentKind = Literal["single", "subscription_initial", "subscription_recurring"]


class CheckoutSession(BaseModel):
    """Returned by `create_checkout_session()` to the API layer."""

    session_id: str = Field(..., description="Adapter-issued session identifier.")
    redirect_url: str = Field(
        ..., description="Where the client should redirect to complete checkout."
    )
    amount_krw: int = Field(..., ge=0, description="Amount in KRW (integer).")
    kind: PaymentKind = Field(
        ..., description="Payment kind (single/subscription/...)."
    )


class PaymentConfirmation(BaseModel):
    """Returned by `confirm_payment()` once a session reaches a terminal state."""

    session_id: str
    status: Literal["succeeded", "failed", "cancelled"]
    paid_at: datetime | None = None
    amount_krw: int = 0


class RefundResult(BaseModel):
    """Returned by `refund()`."""

    payment_id: str
    refunded_amount_krw: int
    status: Literal["refunded", "partially_refunded", "failed"]


class PaymentAdapter(Protocol):
    """Provider-agnostic payment client used by the readings/tarot pipeline."""

    async def create_checkout_session(
        self,
        user_id: str,
        kind: PaymentKind,
        amount_krw: int,
        idempotency_key: str | None = None,
    ) -> CheckoutSession:
        """Issue a new checkout session for `user_id`."""
        ...

    async def confirm_payment(self, session_id: str) -> PaymentConfirmation:
        """Look up the terminal state of a previously-issued session."""
        ...

    async def refund(self, payment_id: str, amount_krw: int) -> RefundResult:
        """Refund (full or partial) a previously-succeeded payment."""
        ...


# ---------------------------------------------------------------------------
# Mock implementation
# ---------------------------------------------------------------------------


# In-process state for the mock: maps session_id → confirmation row that
# gets written by the simulated webhook delay. Tests should call
# `MockPaymentAdapter.reset()` between cases.
_MOCK_SESSIONS: dict[str, PaymentConfirmation] = {}

# Delay (seconds) between session creation and the auto-fired webhook.
# Externalised so tests can patch to 0 to avoid real waits.
MOCK_WEBHOOK_DELAY_SECONDS: float = 3.0


class MockPaymentAdapter:
    """Deterministic payment adapter for Phase 1 PoC.

    - `create_checkout_session()` returns `redirect_url="#mock-success"` and
      a session id derived from `sha256(user_id + idempotency_key)[:32]`, so
      callers pinning to a known id can exercise downstream flows.
    - After ~3 seconds (`MOCK_WEBHOOK_DELAY_SECONDS`), the adapter writes a
      `succeeded` confirmation into the in-process registry. The API layer
      wires this via `BackgroundTasks` so the simulated webhook arrives
      without blocking the request.
    - `confirm_payment()` reads from the same registry; `refund()` produces
      a deterministic `RefundResult` and clears the entry.
    """

    @staticmethod
    def _build_session_id(user_id: str, idempotency_key: str | None) -> str:
        seed = f"{user_id}|{idempotency_key or ''}".encode()
        digest = hashlib.sha256(seed).hexdigest()
        return f"mock-{digest}"[:32]

    async def create_checkout_session(
        self,
        user_id: str,
        kind: PaymentKind,
        amount_krw: int,
        idempotency_key: str | None = None,
    ) -> CheckoutSession:
        session_id = self._build_session_id(user_id, idempotency_key)
        return CheckoutSession(
            session_id=session_id,
            redirect_url="#mock-success",
            amount_krw=amount_krw,
            kind=kind,
        )

    async def fire_webhook(
        self,
        session_id: str,
        amount_krw: int,
        delay_seconds: float | None = None,
    ) -> PaymentConfirmation:
        """Sleep `delay_seconds` then mark the session as succeeded.

        Scheduled via FastAPI `BackgroundTasks` from the checkout endpoint.
        Returning the confirmation lets unit tests await the coroutine
        directly without relying on the background task runner.
        """
        delay = MOCK_WEBHOOK_DELAY_SECONDS if delay_seconds is None else delay_seconds
        if delay > 0:
            await asyncio.sleep(delay)
        confirmation = PaymentConfirmation(
            session_id=session_id,
            status="succeeded",
            paid_at=datetime.now(tz=UTC),
            amount_krw=amount_krw,
        )
        _MOCK_SESSIONS[session_id] = confirmation
        return confirmation

    async def confirm_payment(self, session_id: str) -> PaymentConfirmation:
        confirmation = _MOCK_SESSIONS.get(session_id)
        if confirmation is None:
            return PaymentConfirmation(session_id=session_id, status="failed")
        return confirmation

    async def refund(self, payment_id: str, amount_krw: int) -> RefundResult:
        existing = _MOCK_SESSIONS.get(payment_id)
        status: Literal["refunded", "partially_refunded"]
        if existing is None or amount_krw >= existing.amount_krw:
            status = "refunded"
        else:
            status = "partially_refunded"
        _MOCK_SESSIONS.pop(payment_id, None)
        return RefundResult(
            payment_id=payment_id,
            refunded_amount_krw=amount_krw,
            status=status,
        )

    @classmethod
    def reset(cls) -> None:
        """Test helper: clear the in-process session registry."""
        _MOCK_SESSIONS.clear()


# ---------------------------------------------------------------------------
# Toss stub (Phase 2)
# ---------------------------------------------------------------------------


class TossPaymentAdapter:
    """Phase 2 placeholder. Raises `NotImplementedError` only on first call.

    Importing this class — and instantiating it — must NOT raise so the
    app can boot under `PAYMENT_PROVIDER=toss` even without credentials;
    the failure surfaces at the first business-logic call instead.
    """

    async def create_checkout_session(
        self,
        user_id: str,
        kind: PaymentKind,
        amount_krw: int,
        idempotency_key: str | None = None,
    ) -> CheckoutSession:
        raise NotImplementedError(
            "TossPaymentAdapter.create_checkout_session is a Phase 2 stub. "
            "See ISSUE-043 for the real Toss client implementation."
        )

    async def confirm_payment(self, session_id: str) -> PaymentConfirmation:
        raise NotImplementedError(
            "TossPaymentAdapter.confirm_payment is a Phase 2 stub."
        )

    async def refund(self, payment_id: str, amount_krw: int) -> RefundResult:
        raise NotImplementedError("TossPaymentAdapter.refund is a Phase 2 stub.")


__all__ = [
    "CheckoutSession",
    "MOCK_WEBHOOK_DELAY_SECONDS",
    "MockPaymentAdapter",
    "PaymentAdapter",
    "PaymentConfirmation",
    "PaymentKind",
    "RefundResult",
    "TossPaymentAdapter",
]
