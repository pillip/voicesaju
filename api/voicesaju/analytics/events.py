"""Backend analytics event emitter (ISSUE-080).

Strategy: vendor-agnostic ``AnalyticsBackend`` Protocol with two
default implementations:

- ``NoopAnalyticsBackend`` — drops every event. Default in tests so
  unit suites don't write to logs / external SaaS.
- ``LoggingAnalyticsBackend`` — emits a single ``logger.info`` line per
  event with the event name + sanitised properties. Default in
  dev/staging until a real provider is wired (DEP-XX). Pairs with the
  structured-logging stack (ISSUE-079) so events flow into Logtail.

Adding a real provider (Mixpanel, PostHog, Amplitude) is a matter of
implementing ``AnalyticsBackend.track`` and calling
``set_default_backend`` from ``create_app``.

PRD-Ref: NFR-016. Architecture-Ref: §12.1 (observability stack).
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Protocol

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Event payload
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AnalyticsEvent:
    """Single analytics event row.

    ``name`` is the canonical event slug (e.g. ``payment_completed``)
    and ``properties`` carries the typed payload. ``user_id`` is the
    actor; ``None`` means anonymous (pre-signup events). ``timestamp``
    is UTC and defaults to ``datetime.now`` for convenience but is
    overridable for replay tests.
    """

    name: str
    user_id: str | None
    properties: Mapping[str, Any]
    timestamp: datetime = field(default_factory=lambda: datetime.now(tz=UTC))


# ---------------------------------------------------------------------------
# Backend protocol + implementations
# ---------------------------------------------------------------------------


class AnalyticsBackend(Protocol):
    """Pluggable backend — log, noop, or real vendor SDK."""

    def track(self, event: AnalyticsEvent) -> None:
        """Emit ``event`` synchronously. MUST NOT raise on transport errors."""
        ...


@dataclass
class NoopAnalyticsBackend:
    """Drops every event. Default in unit-test fixtures."""

    received: list[AnalyticsEvent] = field(default_factory=list)

    def track(self, event: AnalyticsEvent) -> None:
        # Even the noop backend records into a list so tests can
        # assert what would have been sent without monkey-patching.
        self.received.append(event)


@dataclass
class LoggingAnalyticsBackend:
    """Default for dev/staging — single structured log line per event."""

    def track(self, event: AnalyticsEvent) -> None:
        try:
            logger.info(
                "analytics.event name=%s user_id=%s properties=%s",
                event.name,
                event.user_id,
                dict(event.properties),
            )
        except Exception as exc:  # noqa: BLE001 — analytics must never crash callers
            logger.warning("analytics backend log emit failed: %s", exc)


# ---------------------------------------------------------------------------
# Process-wide default backend (settable via set_default_backend)
# ---------------------------------------------------------------------------


_default_backend: AnalyticsBackend = NoopAnalyticsBackend()


def get_default_backend() -> AnalyticsBackend:
    """Return the active analytics backend (NoopAnalyticsBackend by default)."""
    return _default_backend


def set_default_backend(backend: AnalyticsBackend) -> None:
    """Swap the active backend — call once from ``create_app`` per env."""
    global _default_backend
    _default_backend = backend


def reset_default_backend_for_tests() -> None:
    """Replace the singleton with a fresh ``NoopAnalyticsBackend``."""
    global _default_backend
    _default_backend = NoopAnalyticsBackend()


# ---------------------------------------------------------------------------
# Emit helpers — typed wrappers callers actually invoke
# ---------------------------------------------------------------------------


def emit_event(
    name: str,
    *,
    user_id: str | None,
    properties: Mapping[str, Any] | None = None,
    backend: AnalyticsBackend | None = None,
) -> None:
    """Emit a generic event. Use only when no typed helper exists.

    Errors are swallowed at the backend layer; this function NEVER
    raises so callers (webhook handlers, request middleware) can treat
    analytics as fire-and-forget.
    """
    active = backend if backend is not None else get_default_backend()
    event = AnalyticsEvent(
        name=name, user_id=user_id, properties=dict(properties or {})
    )
    try:
        active.track(event)
    except Exception as exc:  # noqa: BLE001 — never crash the caller
        logger.warning("analytics emit_event failed name=%s err=%s", name, exc)


def emit_payment_completed(
    *,
    user_id: str,
    payment_id: str,
    amount_krw: int,
    category: str,
    backend: AnalyticsBackend | None = None,
) -> None:
    """Fire ``payment_completed`` after the Toss webhook flips to paid.

    ``category`` is the ``Payment.kind`` value (``single`` or
    ``subscription``) — matches the FR-021 catalogue.
    """
    emit_event(
        "payment_completed",
        user_id=user_id,
        properties={
            "payment_id": payment_id,
            "amount_krw": amount_krw,
            "category": category,
        },
        backend=backend,
    )


def emit_subscription_started(
    *,
    user_id: str,
    subscription_id: str,
    plan: str,
    backend: AnalyticsBackend | None = None,
) -> None:
    """Fire ``subscription_started`` after a subscription becomes active."""
    emit_event(
        "subscription_started",
        user_id=user_id,
        properties={
            "subscription_id": subscription_id,
            "plan": plan,
        },
        backend=backend,
    )


def emit_subscription_cancelled(
    *,
    user_id: str,
    subscription_id: str,
    reason: str | None = None,
    backend: AnalyticsBackend | None = None,
) -> None:
    """Fire ``subscription_cancelled`` after cancellation completes."""
    emit_event(
        "subscription_cancelled",
        user_id=user_id,
        properties={
            "subscription_id": subscription_id,
            "reason": reason,
        },
        backend=backend,
    )


__all__ = [
    "AnalyticsBackend",
    "AnalyticsEvent",
    "LoggingAnalyticsBackend",
    "NoopAnalyticsBackend",
    "emit_event",
    "emit_payment_completed",
    "emit_subscription_cancelled",
    "emit_subscription_started",
    "get_default_backend",
    "reset_default_backend_for_tests",
    "set_default_backend",
]
