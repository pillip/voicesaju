"""Toss Payments confirm-API client (ISSUE-044).

Two implementations live behind a small ``TossClient`` Protocol:

* ``TossHTTPClient`` — real httpx wrapper against
  ``https://api.tosspayments.com/v1/payments/confirm``. Implemented to
  the shape the ISSUE-043 Phase-2 work needs, but its constructor
  refuses to run when ``Settings.toss_secret_key`` is unset so we
  cannot accidentally hit live Toss from a misconfigured Phase-1
  deploy.

* ``MockTossClient`` — Phase-1 default. Delegates to the
  ``MockPaymentAdapter`` in-process registry so the full M2 checkout
  → confirm flow exercises end-to-end without a real merchant.

Selection happens at request time via ``get_toss_client(settings)``
so tests can flip ``PAYMENT_PROVIDER`` per case without restarting
the process.

PRD-Ref: FR-021 (Toss webview integration).
Architecture-Ref: §6.5 (Payment & subscription flow), §11.5 (Toss
API contract — confirm/cancel).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import httpx

from voicesaju.adapters.payment import MockPaymentAdapter
from voicesaju.config import Settings, get_settings

# Default HTTP timeout for the real Toss API. Toss's confirm endpoint
# is usually well under 1s; the 8s cap is generous so a slow Toss
# minute doesn't fail our request entirely.
DEFAULT_TIMEOUT_SECONDS: float = 8.0


@dataclass(frozen=True, slots=True)
class TossConfirmation:
    """Normalised response from the Toss confirm API.

    Both the real HTTP client and the Mock-backed Phase-1 client
    project their respective shapes into this dataclass so the
    payment route only ever sees this canonical envelope.
    """

    order_id: str
    payment_key: str
    status: str
    amount_krw: int
    paid_at: str | None = None


class TossClient(Protocol):
    """Provider-agnostic Toss confirm client used by the payment route."""

    async def confirm_payment(
        self,
        *,
        order_id: str,
        payment_key: str,
        amount_krw: int,
    ) -> TossConfirmation:
        """Confirm *order_id* against the upstream + return the result."""
        ...


# ---------------------------------------------------------------------------
# MockTossClient — Phase-1 default, delegates to MockPaymentAdapter
# ---------------------------------------------------------------------------


class MockTossClient:
    """Phase-1 confirm client backed by :class:`MockPaymentAdapter`.

    The mock adapter keeps its in-process registry keyed by
    ``session_id``; we reuse the registry by passing through
    ``order_id`` as the session id (the checkout route writes
    ``toss_order_id`` and pre-seeds the mock registry so the symmetry
    holds).
    """

    def __init__(self, adapter: MockPaymentAdapter | None = None) -> None:
        # Construct lazily — tests inject their own adapter when they
        # need to control the registry.
        self._adapter = adapter or MockPaymentAdapter()

    async def confirm_payment(
        self,
        *,
        order_id: str,
        payment_key: str,
        amount_krw: int,
    ) -> TossConfirmation:
        """Return the registered confirmation or a synthesised success.

        In production the real Toss API tells us whether the payment
        actually went through. In Phase-1 the MockPaymentAdapter only
        fires its `succeeded` confirmation after a delay; for direct
        confirm() tests we synthesise a successful response inline so
        the route's amount-mismatch path can be exercised deterministically.
        """
        confirmation = await self._adapter.confirm_payment(order_id)
        if confirmation.status == "succeeded" and confirmation.amount_krw > 0:
            return TossConfirmation(
                order_id=order_id,
                payment_key=payment_key,
                status="DONE",
                amount_krw=confirmation.amount_krw,
                paid_at=(
                    confirmation.paid_at.isoformat() if confirmation.paid_at else None
                ),
            )
        # No registry entry (or status≠succeeded) — synthesise a
        # `DONE` response with the caller-supplied amount. This is the
        # Phase-1 lenient path; ISSUE-043 swaps it for a real status
        # lookup against Toss.
        return TossConfirmation(
            order_id=order_id,
            payment_key=payment_key,
            status="DONE",
            amount_krw=amount_krw,
        )

    async def refund_payment(
        self,
        *,
        payment_key: str,
        amount_krw: int,
    ) -> str:
        """Synthesise a Toss-side refund id (ISSUE-076).

        Phase-1 has no real Toss API to call; the automatic refund
        worker (:mod:`voicesaju.jobs.refund_retry`) wires this method
        as its injected ``toss_refund_call``. The return value is the
        synthetic ``toss_refund_id`` written to ``refunds.toss_refund_id``
        — opaque to the caller, deterministic per ``payment_key`` so
        SQLite tests stay reproducible.

        Production (Phase-2) swaps this for
        :meth:`TossHTTPClient.refund_payment` once ISSUE-043 lands the
        merchant credentials. The signature matches the
        ``TossRefundCall`` Protocol (``payment_key``, ``amount_krw`` →
        ``str``) so the swap is a one-line change.
        """
        # Keep the id format aligned with the Toss-side convention
        # (``mock-refund-<payment_key>``) so the integration tests can
        # assert on it without coupling to a UUID factory.
        _ = amount_krw  # noted for parity with TossHTTPClient.refund_payment
        return f"mock-refund-{payment_key}"


# ---------------------------------------------------------------------------
# TossHTTPClient — real httpx wrapper (ISSUE-043 Phase-2)
# ---------------------------------------------------------------------------


class TossHTTPClient:
    """Real Toss confirm client over httpx.

    Uses HTTP Basic auth (`Authorization: Basic base64(secret_key:)` —
    the trailing colon is mandatory per Toss docs). Reads the secret
    key from settings at construction so a Phase-2 deploy without
    credentials surfaces the misconfiguration at startup.
    """

    def __init__(
        self,
        *,
        secret_key: str,
        api_base: str = "https://api.tosspayments.com",
        client: httpx.AsyncClient | None = None,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        if not secret_key:
            raise RuntimeError(
                "TossHTTPClient requires a non-empty toss_secret_key; "
                "set it via env or fall back to PAYMENT_PROVIDER=mock "
                "until ISSUE-043 lands."
            )
        self._secret_key = secret_key
        self._api_base = api_base.rstrip("/")
        self._timeout = timeout_seconds
        # Tests inject their own client so respx can intercept the
        # outbound call without monkey-patching at module level.
        self._client = client

    async def _aclient(self) -> httpx.AsyncClient:
        if self._client is not None:
            return self._client
        # Lazy default client. Reusing one across calls would need an
        # explicit close() — we leave that to the Phase-2 caller.
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(self._timeout),
        )
        return self._client

    async def confirm_payment(
        self,
        *,
        order_id: str,
        payment_key: str,
        amount_krw: int,
    ) -> TossConfirmation:
        client = await self._aclient()
        url = f"{self._api_base}/v1/payments/confirm"
        payload = {
            "orderId": order_id,
            "paymentKey": payment_key,
            "amount": amount_krw,
        }
        response = await client.post(
            url,
            json=payload,
            auth=(self._secret_key, ""),
        )
        response.raise_for_status()
        body = response.json()
        return TossConfirmation(
            order_id=body.get("orderId", order_id),
            payment_key=body.get("paymentKey", payment_key),
            status=body.get("status", "UNKNOWN"),
            amount_krw=int(body.get("totalAmount", amount_krw)),
            paid_at=body.get("approvedAt"),
        )


# ---------------------------------------------------------------------------
# Factory — selects MockTossClient or TossHTTPClient per PAYMENT_PROVIDER
# ---------------------------------------------------------------------------


def get_toss_client(settings: Settings | None = None) -> TossClient:
    """Return the active Toss client.

    Phase-1 default is :class:`MockTossClient`. ``PAYMENT_PROVIDER=toss``
    requires ``Settings.toss_secret_key`` to be set; instantiating the
    real client without it raises ``RuntimeError`` so a misconfigured
    Phase-2 deploy fails loudly at request time.
    """
    settings = settings or get_settings()
    provider = settings.payment_provider.lower()
    if provider == "mock":
        return MockTossClient()
    if provider == "toss":
        # secret_key check happens inside the constructor.
        return TossHTTPClient(
            secret_key=settings.toss_secret_key or "",
            api_base=settings.toss_api_base,
        )
    # Defensive: the Settings literal already constrains the value but
    # we keep an explicit branch in case the union grows.
    raise RuntimeError(
        f"unknown PAYMENT_PROVIDER={settings.payment_provider!r}; "
        "expected 'mock' or 'toss'."
    )


__all__ = [
    "DEFAULT_TIMEOUT_SECONDS",
    "MockTossClient",
    "TossClient",
    "TossConfirmation",
    "TossHTTPClient",
    "get_toss_client",
]
