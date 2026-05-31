"""Observability package — structured logging, tracing, error tracking.

Each sub-module wires one concern:

- ``logging``  — structlog-based JSON logger + PII redaction filter
                 + request_id middleware. (ISSUE-079)
- ``otel``     — OpenTelemetry SDK init + Prometheus /metrics. (ISSUE-077)
- ``sentry``   — Sentry SDK init with PII scrubbing. (ISSUE-078)

The sub-modules are intentionally side-effect-free at import time.
``voicesaju.main.create_app`` decides which initializers to call based
on ``Settings`` flags (``OTEL_ENABLED``, ``SENTRY_DSN``, etc.).
"""
