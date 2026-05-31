"""Structured JSON logging + request_id middleware + PII redaction (ISSUE-079).

Architecture §12.1 calls for:

- JSON to stdout, shipped by container runtime to Logtail/Better Stack.
- Required fields: ``timestamp``, ``level``, ``service``, ``request_id``,
  ``user_id?``, ``device_id?``, ``route``, ``event``.
- A PII redaction filter that strips ``birth_dt``, payment keys, Toss
  order IDs, and JWT tokens before any event reaches the wire.

This module is import-time-safe. Call :func:`configure_logging` once
from :func:`voicesaju.main.create_app` and attach
:class:`RequestIdMiddleware` to inject ``request_id`` per request.

PRD-Ref: NFR-005, OWASP A09.
"""

from __future__ import annotations

import logging
import re
import sys
import uuid
from contextvars import ContextVar
from typing import Any

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

# ---------------------------------------------------------------------------
# Request-scoped context vars. ``request_id`` is set by RequestIdMiddleware
# on every request; structlog's ContextVar processor reads them when an
# event is logged so callers don't have to thread the id manually.
# ---------------------------------------------------------------------------

_request_id_ctx: ContextVar[str | None] = ContextVar("request_id", default=None)
_route_ctx: ContextVar[str | None] = ContextVar("route", default=None)

REDACTED = "[REDACTED]"

# PII keys that should never appear in event values. Matches are
# case-insensitive on key name. The middleware-injected ``request_id``,
# ``route``, and ``event`` are explicitly NOT redacted.
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

# Patterns redacted in free-text string values. Each pattern targets a
# specific shape so we don't accidentally redact unrelated copy.
#
# - ``birth_dt`` style ISO-8601 (1989-04-12, 1989-04-12T03:30, …)
# - Toss order IDs (``ORD-`` / ``ord_`` / ``MC4F-...`` 6+ char alnum)
# - Toss paymentKey (32+ hex/alnum chars after ``paymentKey=`` or as JSON)
# - JWT tokens (3 dot-separated base64url segments)
_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    # JWT: header.payload.signature — each segment is base64url
    (
        re.compile(
            r"\beyJ[A-Za-z0-9_-]+={0,2}\.[A-Za-z0-9_-]+={0,2}\.[A-Za-z0-9_-]+={0,2}\b"
        ),
        REDACTED,
    ),
    # Toss order id: ORD-… / ord_… (case-insensitive prefix, alnum body)
    (re.compile(r"\b(?:ORD[-_])[A-Za-z0-9_-]{6,}\b"), REDACTED),
    # Toss paymentKey value: long alnum string adjacent to the key name.
    # The leading capture preserves the surrounding ``paymentKey":"`` /
    # ``paymentKey=`` / ``paymentKey: "...`` so the JSON shape stays
    # valid for downstream parsers. The class ``["':= ]+`` greedily
    # eats whatever separator sits between the key name and the value;
    # we don't need to match the trailing quote because we never emit
    # one — the next char after the captured prefix is the redaction.
    (
        re.compile(
            r"(paymentKey[\"':= ]+)[A-Za-z0-9_-]{16,}",
            re.IGNORECASE,
        ),
        rf"\1{REDACTED}",
    ),
    # birth_dt= / "birth_dt": ISO date
    (
        re.compile(
            r"(birth[_-]?(?:dt|date)\s*[=:]\s*[\"']?)"
            r"\d{4}-\d{2}-\d{2}(?:[T ]\d{2}:\d{2}(?::\d{2})?)?",
            re.IGNORECASE,
        ),
        rf"\1{REDACTED}",
    ),
)


def redact(value: Any) -> Any:
    """Strip known PII patterns from ``value`` recursively.

    - ``dict`` — every key matching ``_SENSITIVE_KEYS`` (case-insensitive)
      has its value replaced with :data:`REDACTED`. Other values recurse.
    - ``list`` / ``tuple`` — element-wise recurse.
    - ``str``  — every regex in ``_PATTERNS`` is applied.
    - ``bytes`` / numbers / booleans / ``None`` — returned unchanged.

    The function is total (never raises). Unknown types pass through.
    """
    if value is None or isinstance(value, (bool, int, float, bytes)):
        return value
    if isinstance(value, str):
        out = value
        for pattern, replacement in _PATTERNS:
            out = pattern.sub(replacement, out)
        return out
    if isinstance(value, dict):
        return {
            k: (
                REDACTED
                if isinstance(k, str) and k.lower() in _SENSITIVE_KEYS
                else redact(v)
            )
            for k, v in value.items()
        }
    if isinstance(value, (list, tuple)):
        cleaned = [redact(item) for item in value]
        return type(value)(cleaned) if isinstance(value, tuple) else cleaned
    return value


def _redaction_processor(
    _logger: Any, _method: str, event_dict: dict[str, Any]
) -> dict[str, Any]:
    """structlog processor — runs :func:`redact` over the whole event dict."""
    return redact(event_dict)


def _inject_context(
    _logger: Any, _method: str, event_dict: dict[str, Any]
) -> dict[str, Any]:
    """Inject request_id / route from ContextVars into the event dict."""
    request_id = _request_id_ctx.get()
    if request_id and "request_id" not in event_dict:
        event_dict["request_id"] = request_id
    route = _route_ctx.get()
    if route and "route" not in event_dict:
        event_dict["route"] = route
    return event_dict


def configure_logging(
    *,
    service_name: str = "voicesaju-api",
    log_level: str = "INFO",
) -> None:
    """Configure stdlib logging + structlog with the JSON renderer.

    Idempotent — calling twice is safe. ``service_name`` is added as a
    bound field so every event carries it without callers needing to set
    it explicitly.
    """
    level_value = getattr(logging, log_level.upper(), logging.INFO)

    # Replace any existing handlers so test reruns don't pile up.
    root = logging.getLogger()
    root.handlers = [logging.StreamHandler(sys.stdout)]
    root.setLevel(level_value)
    # The stdlib formatter is bypassed — structlog writes the final JSON
    # via the StreamHandler's stream directly.
    for handler in root.handlers:
        handler.setFormatter(logging.Formatter("%(message)s"))

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            _inject_context,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            _redaction_processor,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level_value),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Bind service_name globally so every event carries it.
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(service=service_name)


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """Return a bound structlog logger. ``name`` becomes the ``logger`` field."""
    return structlog.get_logger(name) if name else structlog.get_logger()


def get_request_id() -> str | None:
    """Return the current request's request_id (or ``None`` if outside a request)."""
    return _request_id_ctx.get()


class RequestIdMiddleware(BaseHTTPMiddleware):
    """Inject a per-request ``request_id`` ContextVar + response header.

    - If the inbound request carries ``X-Request-ID``, that value is
      honoured (caps at 64 chars, alnum/dash/underscore only).
    - Otherwise a fresh ``uuid4().hex`` is generated.
    - The id is also echoed back on the response as ``X-Request-ID`` so
      clients can correlate.
    """

    _HEADER_NAME = "X-Request-ID"
    _ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,64}$")

    async def dispatch(self, request: Request, call_next) -> Response:
        incoming = request.headers.get(self._HEADER_NAME)
        if incoming and self._ID_PATTERN.match(incoming):
            request_id = incoming
        else:
            request_id = uuid.uuid4().hex

        token = _request_id_ctx.set(request_id)
        route_token = _route_ctx.set(request.url.path)
        try:
            response = await call_next(request)
        finally:
            _request_id_ctx.reset(token)
            _route_ctx.reset(route_token)

        response.headers[self._HEADER_NAME] = request_id
        return response


__all__ = [
    "REDACTED",
    "RequestIdMiddleware",
    "configure_logging",
    "get_logger",
    "get_request_id",
    "redact",
]
