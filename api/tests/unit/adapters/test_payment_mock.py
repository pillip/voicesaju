"""Unit tests for MockPaymentAdapter + adapter factory."""

from __future__ import annotations

import asyncio
import hashlib

import pytest

from voicesaju.adapters import UnknownProviderError, get_payment_adapter
from voicesaju.adapters.payment import (
    CheckoutSession,
    MockPaymentAdapter,
    PaymentConfirmation,
    RefundResult,
    TossPaymentAdapter,
)
from voicesaju.config import Settings


def test_factory_returns_mock_when_provider_is_mock() -> None:
    settings = Settings(payment_provider="mock")
    adapter = get_payment_adapter(settings)
    assert isinstance(adapter, MockPaymentAdapter)


def test_factory_returns_toss_stub_when_provider_is_toss() -> None:
    settings = Settings(payment_provider="toss")
    adapter = get_payment_adapter(settings)
    assert isinstance(adapter, TossPaymentAdapter)


def test_factory_unknown_provider_raises_on_use() -> None:
    """Unknown provider names must surface a clear error."""
    settings = Settings()
    # Bypass Literal validation by writing through the underlying attribute.
    # In production, pydantic-settings rejects unknowns; this guards the
    # factory's own validation as a safety net.
    object.__setattr__(settings, "payment_provider", "bogus")
    with pytest.raises(UnknownProviderError):
        get_payment_adapter(settings)


def test_mock_create_checkout_session_returns_redirect_url() -> None:
    adapter = MockPaymentAdapter()
    session = asyncio.run(
        adapter.create_checkout_session(
            user_id="user-1",
            kind="single",
            amount_krw=4900,
            idempotency_key="idem-1",
        )
    )
    assert isinstance(session, CheckoutSession)
    assert session.redirect_url == "#mock-success"
    assert session.amount_krw == 4900
    assert session.kind == "single"
    assert session.session_id.startswith("mock-")


def test_mock_session_id_is_deterministic() -> None:
    """Same (user_id, idempotency_key) tuple must produce the same session_id."""
    adapter = MockPaymentAdapter()
    s1 = asyncio.run(
        adapter.create_checkout_session(
            user_id="user-42",
            kind="single",
            amount_krw=4900,
            idempotency_key="idem-xyz",
        )
    )
    s2 = asyncio.run(
        adapter.create_checkout_session(
            user_id="user-42",
            kind="single",
            amount_krw=4900,
            idempotency_key="idem-xyz",
        )
    )
    assert s1.session_id == s2.session_id

    # Expected digest = sha256("user-42|idem-xyz")[:32 chars after 'mock-' prefix]
    digest = hashlib.sha256(b"user-42|idem-xyz").hexdigest()
    expected = f"mock-{digest}"[:32]
    assert s1.session_id == expected


def test_mock_session_id_differs_for_different_idempotency_keys() -> None:
    adapter = MockPaymentAdapter()
    s1 = asyncio.run(
        adapter.create_checkout_session(
            user_id="u", kind="single", amount_krw=1, idempotency_key="a"
        )
    )
    s2 = asyncio.run(
        adapter.create_checkout_session(
            user_id="u", kind="single", amount_krw=1, idempotency_key="b"
        )
    )
    assert s1.session_id != s2.session_id


def test_mock_webhook_marks_session_succeeded() -> None:
    """Awaiting fire_webhook with delay=0 must record a succeeded confirmation."""
    adapter = MockPaymentAdapter()
    MockPaymentAdapter.reset()

    session = asyncio.run(
        adapter.create_checkout_session(
            user_id="u", kind="single", amount_krw=4900, idempotency_key="w1"
        )
    )
    confirmation = asyncio.run(
        adapter.fire_webhook(
            session_id=session.session_id, amount_krw=4900, delay_seconds=0
        )
    )

    assert isinstance(confirmation, PaymentConfirmation)
    assert confirmation.status == "succeeded"
    assert confirmation.paid_at is not None
    assert confirmation.amount_krw == 4900

    # confirm_payment reads from the same registry.
    looked_up = asyncio.run(adapter.confirm_payment(session.session_id))
    assert looked_up.status == "succeeded"


def test_mock_confirm_unknown_session_returns_failed() -> None:
    adapter = MockPaymentAdapter()
    MockPaymentAdapter.reset()
    result = asyncio.run(adapter.confirm_payment("mock-doesnotexist"))
    assert result.status == "failed"


def test_mock_refund_full() -> None:
    adapter = MockPaymentAdapter()
    MockPaymentAdapter.reset()
    session = asyncio.run(
        adapter.create_checkout_session(
            user_id="u", kind="single", amount_krw=4900, idempotency_key="r1"
        )
    )
    asyncio.run(
        adapter.fire_webhook(session.session_id, amount_krw=4900, delay_seconds=0)
    )
    result = asyncio.run(adapter.refund(session.session_id, amount_krw=4900))
    assert isinstance(result, RefundResult)
    assert result.status == "refunded"
    assert result.refunded_amount_krw == 4900


def test_mock_refund_partial() -> None:
    adapter = MockPaymentAdapter()
    MockPaymentAdapter.reset()
    session = asyncio.run(
        adapter.create_checkout_session(
            user_id="u", kind="single", amount_krw=4900, idempotency_key="p1"
        )
    )
    asyncio.run(
        adapter.fire_webhook(session.session_id, amount_krw=4900, delay_seconds=0)
    )
    result = asyncio.run(adapter.refund(session.session_id, amount_krw=1000))
    assert result.status == "partially_refunded"
    assert result.refunded_amount_krw == 1000


def test_toss_adapter_import_does_not_raise() -> None:
    """Importing/instantiating must succeed even without credentials."""
    adapter = TossPaymentAdapter()
    assert adapter is not None  # no exception


def test_toss_create_checkout_raises_not_implemented() -> None:
    adapter = TossPaymentAdapter()
    with pytest.raises(NotImplementedError):
        asyncio.run(
            adapter.create_checkout_session(user_id="u", kind="single", amount_krw=4900)
        )


def test_toss_confirm_payment_raises_not_implemented() -> None:
    adapter = TossPaymentAdapter()
    with pytest.raises(NotImplementedError):
        asyncio.run(adapter.confirm_payment("any-session"))


def test_toss_refund_raises_not_implemented() -> None:
    adapter = TossPaymentAdapter()
    with pytest.raises(NotImplementedError):
        asyncio.run(adapter.refund("any-payment", 1000))
