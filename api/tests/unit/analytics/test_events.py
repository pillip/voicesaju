"""Unit tests for the backend analytics event SDK (ISSUE-080).

PRD-Ref: NFR-016.
"""

from __future__ import annotations

import logging

import pytest

from voicesaju.analytics import (
    AnalyticsEvent,
    LoggingAnalyticsBackend,
    NoopAnalyticsBackend,
    emit_event,
    emit_payment_completed,
    emit_subscription_cancelled,
    emit_subscription_started,
    get_default_backend,
    reset_default_backend_for_tests,
    set_default_backend,
)


@pytest.fixture(autouse=True)
def _reset_backend() -> None:
    reset_default_backend_for_tests()


# ---------------------------------------------------------------------------
# AnalyticsEvent dataclass
# ---------------------------------------------------------------------------


def test_analytics_event_carries_required_fields() -> None:
    """Event is constructed with name, user_id, and properties payload."""
    ev = AnalyticsEvent(name="x", user_id="u1", properties={"a": 1})
    assert ev.name == "x"
    assert ev.user_id == "u1"
    assert ev.properties == {"a": 1}
    assert ev.timestamp is not None


def test_analytics_event_allows_anonymous() -> None:
    """``user_id=None`` is valid — pre-signup funnel events."""
    ev = AnalyticsEvent(name="signup", user_id=None, properties={})
    assert ev.user_id is None


# ---------------------------------------------------------------------------
# Default backend wiring
# ---------------------------------------------------------------------------


def test_default_backend_is_noop_after_reset() -> None:
    """Test fixtures get a fresh NoopAnalyticsBackend each run."""
    backend = get_default_backend()
    assert isinstance(backend, NoopAnalyticsBackend)


def test_set_default_backend_swaps_singleton() -> None:
    """``set_default_backend`` replaces the active backend in-place."""
    new_backend = LoggingAnalyticsBackend()
    set_default_backend(new_backend)
    assert get_default_backend() is new_backend


# ---------------------------------------------------------------------------
# emit_event — generic path
# ---------------------------------------------------------------------------


def test_emit_event_records_into_default_noop_backend() -> None:
    """Events flow through the default NoopAnalyticsBackend's receipt list."""
    emit_event("paywall_view", user_id="u1", properties={"price_krw": 4900})
    backend = get_default_backend()
    assert isinstance(backend, NoopAnalyticsBackend)
    assert len(backend.received) == 1
    ev = backend.received[0]
    assert ev.name == "paywall_view"
    assert ev.user_id == "u1"
    assert ev.properties == {"price_krw": 4900}


def test_emit_event_uses_injected_backend_when_provided() -> None:
    """Explicit ``backend=`` overrides the singleton (per-call override)."""
    explicit = NoopAnalyticsBackend()
    emit_event("x", user_id="u", properties={}, backend=explicit)
    assert len(explicit.received) == 1
    assert explicit.received[0].name == "x"
    # Default backend was untouched.
    assert get_default_backend().received == []  # type: ignore[attr-defined]


def test_emit_event_swallows_backend_errors() -> None:
    """Backend exceptions never propagate — analytics is fire-and-forget."""

    class _BrokenBackend:
        def track(self, event):  # type: ignore[no-untyped-def]
            raise RuntimeError("vendor down")

    # Should NOT raise.
    emit_event("x", user_id=None, properties={}, backend=_BrokenBackend())


# ---------------------------------------------------------------------------
# Typed helpers — AC mapping
# ---------------------------------------------------------------------------


def test_emit_payment_completed_carries_amount_and_category() -> None:
    """AC3: ``payment_completed`` event includes amount + category."""
    backend = NoopAnalyticsBackend()
    emit_payment_completed(
        user_id="u-42",
        payment_id="pay_abc",
        amount_krw=4900,
        category="single",
        backend=backend,
    )
    assert len(backend.received) == 1
    ev = backend.received[0]
    assert ev.name == "payment_completed"
    assert ev.user_id == "u-42"
    assert ev.properties["payment_id"] == "pay_abc"
    assert ev.properties["amount_krw"] == 4900
    assert ev.properties["category"] == "single"


def test_emit_subscription_started_includes_plan() -> None:
    backend = NoopAnalyticsBackend()
    emit_subscription_started(
        user_id="u-1",
        subscription_id="sub_x",
        plan="monthly",
        backend=backend,
    )
    assert backend.received[0].name == "subscription_started"
    assert backend.received[0].properties == {
        "subscription_id": "sub_x",
        "plan": "monthly",
    }


def test_emit_subscription_cancelled_allows_optional_reason() -> None:
    backend = NoopAnalyticsBackend()
    emit_subscription_cancelled(
        user_id="u-1",
        subscription_id="sub_x",
        backend=backend,
    )
    assert backend.received[0].properties == {
        "subscription_id": "sub_x",
        "reason": None,
    }

    emit_subscription_cancelled(
        user_id="u-1",
        subscription_id="sub_x",
        reason="billing_failed",
        backend=backend,
    )
    assert backend.received[1].properties["reason"] == "billing_failed"


# ---------------------------------------------------------------------------
# LoggingAnalyticsBackend
# ---------------------------------------------------------------------------


def test_logging_backend_emits_info_log(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """``LoggingAnalyticsBackend`` writes a single info line per event."""
    backend = LoggingAnalyticsBackend()
    caplog.set_level(logging.INFO, logger="voicesaju.analytics.events")
    backend.track(
        AnalyticsEvent(name="paywall_pay", user_id="u-9", properties={"amount": 9900})
    )
    matched = [
        r
        for r in caplog.records
        if r.name == "voicesaju.analytics.events" and "analytics.event" in r.message
    ]
    assert (
        matched
    ), f"Expected analytics.event log; got {[r.message for r in caplog.records]}"


def test_logging_backend_does_not_raise_on_malformed_properties() -> None:
    """LoggingBackend wraps emit in try/except so it cannot crash callers."""
    backend = LoggingAnalyticsBackend()

    class _Bad:
        def __repr__(self) -> str:
            raise RuntimeError("boom")

    # Even with an object that explodes on repr, no exception leaks.
    backend.track(AnalyticsEvent(name="x", user_id=None, properties={"bad": _Bad()}))


# ---------------------------------------------------------------------------
# Noop receipt log helps test integration
# ---------------------------------------------------------------------------


def test_noop_backend_records_for_assertion_friendliness() -> None:
    """NoopAnalyticsBackend captures events so tests can introspect."""
    backend = NoopAnalyticsBackend()
    backend.track(AnalyticsEvent(name="a", user_id=None, properties={}))
    backend.track(AnalyticsEvent(name="b", user_id="u", properties={}))
    assert [e.name for e in backend.received] == ["a", "b"]
