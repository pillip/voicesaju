"""Tracing shim — OpenTelemetry-style spans without a hard dependency.

ISSUE-039 calls for per-stage OTel spans on the reading pipeline
(``chart_lookup``, ``llm_stream``, ``guardrail``, ``tts_stream``,
``r2_upload``, ``sse_emit``). The full ``opentelemetry-api`` install is
deferred to the post-M2 observability pass — until then we ship a tiny
no-op-by-default ``tracer`` so the pipeline call sites stay stable
across the swap.

Usage::

    from voicesaju.tracing import tracer

    with tracer.start_span("pipeline.chart_lookup") as span:
        span.set_attribute("category", category)
        ...

When the real OTel SDK lands, this module can either re-export
``opentelemetry.trace.get_tracer`` directly or keep the same shape but
delegate. The pipeline does NOT import from ``opentelemetry`` at
runtime so swapping is contained to this file.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any


class _NoopSpan:
    """Span stand-in that accepts attribute/event calls and ignores them."""

    __slots__ = ("name",)

    def __init__(self, name: str) -> None:
        self.name = name

    def set_attribute(self, key: str, value: Any) -> None:
        """No-op until a real OTel exporter is wired."""
        del key, value

    def add_event(self, name: str, attributes: dict[str, Any] | None = None) -> None:
        """No-op until a real OTel exporter is wired."""
        del name, attributes

    def record_exception(self, exc: BaseException) -> None:
        """No-op until a real OTel exporter is wired."""
        del exc

    def set_status(self, status: str, description: str | None = None) -> None:
        """No-op until a real OTel exporter is wired."""
        del status, description


class _NoopTracer:
    """Tracer stand-in. ``start_span()`` yields a ``_NoopSpan``."""

    @contextmanager
    def start_span(self, name: str):
        """Yield a no-op span for *name*. Mirrors OTel's context-manager API."""
        yield _NoopSpan(name)


# Module-level singleton. Importers do ``from voicesaju.tracing import tracer``.
tracer = _NoopTracer()


__all__ = ["tracer"]
