"""Sentry SDK init + PII scrubbing (ISSUE-078).

Architecture §12 calls for Sentry on errors. Architecture §11 + NFR-005
forbid PII (birth dates, payment keys, Toss order IDs) from leaving the
backend in any telemetry stream — including error reports.

Init is gated by ``Settings.sentry_dsn``: when unset the SDK is never
initialised, so ``import voicesaju.observability.sentry`` has zero
runtime impact in tests and local dev.

PRD-Ref: NFR-016 (uptime / error visibility).
"""

from __future__ import annotations

import re
from typing import Any

import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.starlette import StarletteIntegration

# Keys that must never leave the backend in a Sentry event. Lowercased
# during comparison so ``Birth_DT`` and ``paymentKey`` are caught too.
_SENSITIVE_KEYS: frozenset[str] = frozenset(
    {
        "birth_dt",
        "birth_date",
        "birthdate",
        "birth",
        "payment_key",
        "paymentkey",
        "card_number",
        "cardnumber",
        "card_no",
        "cvv",
        "secret_key",
        "secretkey",
        "api_key",
        "apikey",
        "access_token",
        "refresh_token",
        "jwt",
        "authorization",
        "password",
        "passwd",
    }
)

REDACTED = "[REDACTED]"

# String-shape patterns we never want to ship to Sentry. We re-use the
# same families as the logging redactor (ISSUE-079) so the two filters
# stay consistent; we don't import from logging.py to keep this module
# usable even before logging is configured.
_STRING_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (
        re.compile(
            r"\beyJ[A-Za-z0-9_-]+={0,2}\.[A-Za-z0-9_-]+={0,2}\.[A-Za-z0-9_-]+={0,2}\b"
        ),
        REDACTED,
    ),
    (re.compile(r"\b(?:ORD[-_])[A-Za-z0-9_-]{6,}\b"), REDACTED),
    (
        re.compile(
            r"(paymentKey[\"':= ]+)[A-Za-z0-9_-]{16,}",
            re.IGNORECASE,
        ),
        rf"\1{REDACTED}",
    ),
    (
        re.compile(
            r"(birth[_-]?(?:dt|date)\s*[=:]\s*[\"']?)"
            r"\d{4}-\d{2}-\d{2}(?:[T ]\d{2}:\d{2}(?::\d{2})?)?",
            re.IGNORECASE,
        ),
        rf"\1{REDACTED}",
    ),
)


def _scrub_value(value: Any) -> Any:
    """Recursively scrub PII from any JSON-like value."""
    if value is None or isinstance(value, (bool, int, float, bytes)):
        return value
    if isinstance(value, str):
        out = value
        for pattern, replacement in _STRING_PATTERNS:
            out = pattern.sub(replacement, out)
        return out
    if isinstance(value, dict):
        return {
            k: (
                REDACTED
                if isinstance(k, str) and k.lower() in _SENSITIVE_KEYS
                else _scrub_value(v)
            )
            for k, v in value.items()
        }
    if isinstance(value, (list, tuple)):
        cleaned = [_scrub_value(item) for item in value]
        return type(value)(cleaned) if isinstance(value, tuple) else cleaned
    return value


def scrub_event(
    event: dict[str, Any], _hint: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Sentry ``before_send`` callback — scrub PII from the event tree.

    Returns the (possibly mutated) event dict so Sentry transmits the
    redacted copy. We never return ``None`` (which would drop the event)
    — visibility of an error is more valuable than fully suppressing it.
    """
    return _scrub_value(event)


def init_sentry(
    *,
    dsn: str | None,
    environment: str = "local",
    release: str | None = None,
    traces_sample_rate: float = 0.0,
) -> bool:
    """Initialise the Sentry SDK if ``dsn`` is set.

    Returns ``True`` iff initialisation actually happened. The factory
    in :func:`voicesaju.main.create_app` uses the return value only for
    logging; absence of a DSN is the normal path in local/test runs.

    The init pins ``send_default_pii=False`` and registers
    :func:`scrub_event` as the ``before_send`` hook so even if a user-
    supplied PII field slips past the regular logging filter, it is
    redacted before transmission.
    """
    if not dsn:
        return False

    sentry_sdk.init(
        dsn=dsn,
        environment=environment,
        release=release,
        send_default_pii=False,
        # Keep traces opt-in — the OTel pipeline (ISSUE-077) is the
        # primary trace backend; Sentry traces are a backup only.
        traces_sample_rate=traces_sample_rate,
        integrations=[
            FastApiIntegration(transaction_style="endpoint"),
            StarletteIntegration(transaction_style="endpoint"),
        ],
        before_send=scrub_event,
    )
    return True


__all__ = [
    "REDACTED",
    "init_sentry",
    "scrub_event",
]
