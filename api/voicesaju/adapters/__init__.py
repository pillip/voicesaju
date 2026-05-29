"""Adapter factories.

Adapter selection is driven by `Settings` env vars (e.g. `PAYMENT_PROVIDER`)
so tests, local-dev and prod each get the right backend without code changes.
The Phase 1 PoC stack runs entirely on `*_PROVIDER=mock` so the full vertical
slice exercises without external API credentials (see ISSUE-099..102).
"""

from __future__ import annotations

from voicesaju.adapters.payment import (
    MockPaymentAdapter,
    PaymentAdapter,
    TossPaymentAdapter,
)
from voicesaju.config import Settings, get_settings


class UnknownProviderError(RuntimeError):
    """Raised when the configured provider name is not recognised."""


def get_payment_adapter(settings: Settings | None = None) -> PaymentAdapter:
    """Return the active payment adapter selected by `settings.payment_provider`.

    Phase 1 default is `mock`. `toss` returns a stub whose methods raise
    `NotImplementedError` only on first call so the app still boots when the
    env points at a real provider but credentials are missing.
    """
    settings = settings or get_settings()
    provider = settings.payment_provider.lower()
    if provider == "mock":
        return MockPaymentAdapter()
    if provider == "toss":
        return TossPaymentAdapter()
    raise UnknownProviderError(
        f"unknown PAYMENT_PROVIDER={settings.payment_provider!r}; "
        "expected one of: 'mock', 'toss'"
    )


__all__ = [
    "MockPaymentAdapter",
    "PaymentAdapter",
    "TossPaymentAdapter",
    "UnknownProviderError",
    "get_payment_adapter",
]
