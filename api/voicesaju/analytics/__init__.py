"""Backend analytics SDK (ISSUE-080).

Phase-1 ships a vendor-agnostic emitter so we can wire business-event
calls into the webhook + subscription flows without committing to a
specific SaaS (Mixpanel, PostHog, Amplitude — DEP-XX). The real
provider integration slots in by replacing the default
``LoggingAnalyticsBackend`` with a vendor-specific implementation.

Public surface:
- ``emit_payment_completed(payment_id, user_id, amount_krw, category)``
- ``emit_subscription_started(user_id, subscription_id, plan)``
- ``emit_subscription_cancelled(user_id, subscription_id, reason)``

PRD-Ref: NFR-016 (success metrics).
"""

from voicesaju.analytics.events import (
    AnalyticsBackend,
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
