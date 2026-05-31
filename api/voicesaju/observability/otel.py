"""OpenTelemetry SDK init + Prometheus ``/metrics`` route (ISSUE-077).

Architecture §12.2 / §12.3 calls for:

- An OTel ``TracerProvider`` with OTLP export when ``OTEL_ENABLED=true``,
  feeding the same custom spans already emitted in the reading + tarot
  pipelines through the existing :mod:`voicesaju.tracing` shim.
- Auto-instrumentation for FastAPI + httpx so per-request spans bracket
  every endpoint and downstream HTTP call.
- Prometheus exposition format on ``/metrics`` covering the three SLO
  histograms: ``reading_pipeline_e2e_seconds``, ``tts_first_chunk_seconds``,
  ``llm_call_duration_seconds``.

Init is gated by ``Settings.otel_enabled``: when false the SDK is never
configured and the existing :mod:`voicesaju.tracing` no-op shim keeps
delivering. When true, ``configure_otel`` swaps the shim's internal
``tracer`` for the real OTel tracer; call sites (``pipeline_service``,
``tarot_pipeline_service``) require no edits.

PRD-Ref: NFR-001, NFR-002, NFR-003, NFR-004, NFR-011, NFR-016.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager, suppress  # noqa: F401 -- suppress used below
from typing import Any

from fastapi import FastAPI
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import SpanProcessor, TracerProvider
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
    SimpleSpanProcessor,
)
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    Histogram,
    generate_latest,
)
from starlette.requests import Request
from starlette.responses import Response

# ---------------------------------------------------------------------------
# Prometheus registry + the three SLO histograms. We keep our own
# ``CollectorRegistry`` so multiple ``configure_otel`` calls (e.g. in
# tests) don't double-register.
# ---------------------------------------------------------------------------

# Bucket boundaries chosen against the NFR SLO targets:
# - reading_pipeline_e2e_seconds → 3s warn / 5s page → buckets cover 1-10s.
# - tts_first_chunk_seconds → 1.5s warn / 3s page → buckets cover 0.25-5s.
# - llm_call_duration_seconds → mostly <2s; buckets cover 0.5-30s.
_E2E_BUCKETS: tuple[float, ...] = (
    0.5,
    1.0,
    1.5,
    2.0,
    2.5,
    3.0,
    4.0,
    5.0,
    7.5,
    10.0,
)
_TTS_BUCKETS: tuple[float, ...] = (
    0.25,
    0.5,
    0.75,
    1.0,
    1.5,
    2.0,
    3.0,
    5.0,
)
_LLM_BUCKETS: tuple[float, ...] = (
    0.5,
    1.0,
    2.0,
    3.0,
    5.0,
    10.0,
    20.0,
    30.0,
)

# Module-level singletons. Built once on import so tests can introspect
# them via ``METRICS_REGISTRY`` without re-running ``configure_otel``.
METRICS_REGISTRY = CollectorRegistry()

READING_PIPELINE_E2E_SECONDS = Histogram(
    "reading_pipeline_e2e_seconds",
    "End-to-end wall time of the reading pipeline (chart→LLM→TTS→R2→SSE).",
    buckets=_E2E_BUCKETS,
    registry=METRICS_REGISTRY,
)
TTS_FIRST_CHUNK_SECONDS = Histogram(
    "tts_first_chunk_seconds",
    "Time from TTS request start to first audio chunk delivered to the client.",
    buckets=_TTS_BUCKETS,
    registry=METRICS_REGISTRY,
)
LLM_CALL_DURATION_SECONDS = Histogram(
    "llm_call_duration_seconds",
    "Duration of a single LLM streaming call (start to terminal token).",
    labelnames=("model", "kind"),
    buckets=_LLM_BUCKETS,
    registry=METRICS_REGISTRY,
)


# ---------------------------------------------------------------------------
# Tracer state. We hold a single ``TracerProvider`` when OTel is enabled,
# and expose a context-manager helper that mirrors the existing
# :mod:`voicesaju.tracing` API so pipeline call sites keep working.
# ---------------------------------------------------------------------------

_PROVIDER: TracerProvider | None = None
_IN_MEMORY_EXPORTER: InMemorySpanExporter | None = None


class _OTelSpanAdapter:
    """Adapter that wraps an OTel ``Span`` in the existing shim API.

    The legacy shim exposes ``set_attribute``, ``add_event``,
    ``record_exception``, ``set_status``. We re-implement the surface so
    pipeline modules can keep importing from :mod:`voicesaju.tracing`
    without knowing whether the real SDK is wired or not.
    """

    __slots__ = ("_span",)

    def __init__(self, span: trace.Span) -> None:
        self._span = span

    def set_attribute(self, key: str, value: Any) -> None:
        self._span.set_attribute(key, value)

    def add_event(self, name: str, attributes: dict[str, Any] | None = None) -> None:
        self._span.add_event(name, attributes=attributes or {})

    def record_exception(self, exc: BaseException) -> None:
        self._span.record_exception(exc)

    def set_status(self, status: str, description: str | None = None) -> None:
        # The legacy shim accepts free-form status strings; map "ok" /
        # "error" / anything else to the OTel ``StatusCode`` enum.
        from opentelemetry.trace.status import Status, StatusCode

        code = (
            StatusCode.OK
            if status.lower() == "ok"
            else StatusCode.ERROR
            if status.lower() == "error"
            else StatusCode.UNSET
        )
        self._span.set_status(Status(code, description=description))


class _OTelTracerWrapper:
    """Mirrors the shim's ``start_span`` API on top of an OTel tracer."""

    __slots__ = ("_tracer",)

    def __init__(self, tracer: trace.Tracer) -> None:
        self._tracer = tracer

    @contextmanager
    def start_span(self, name: str) -> Iterator[_OTelSpanAdapter]:
        with self._tracer.start_as_current_span(name) as span:
            yield _OTelSpanAdapter(span)


def configure_otel(
    *,
    enabled: bool,
    endpoint: str | None,
    service_name: str = "voicesaju-api",
    environment: str = "local",
    use_in_memory_exporter: bool = False,
) -> bool:
    """Initialise the OTel SDK and swap the shim's tracer.

    Returns ``True`` iff initialisation actually happened. When
    ``enabled`` is false the function is a no-op and the existing
    :mod:`voicesaju.tracing` shim continues delivering no-op spans.

    ``use_in_memory_exporter`` is reserved for the integration tests —
    spans are captured in :data:`_IN_MEMORY_EXPORTER` so callers can
    assert against them deterministically.
    """
    global _PROVIDER, _IN_MEMORY_EXPORTER

    if not enabled:
        return False

    resource = Resource.create(
        {
            "service.name": service_name,
            "deployment.environment": environment,
        }
    )
    provider = TracerProvider(resource=resource)

    if use_in_memory_exporter:
        _IN_MEMORY_EXPORTER = InMemorySpanExporter()
        processor: SpanProcessor = SimpleSpanProcessor(_IN_MEMORY_EXPORTER)
    else:
        exporter = (
            OTLPSpanExporter(endpoint=endpoint) if endpoint else OTLPSpanExporter()
        )
        processor = BatchSpanProcessor(exporter)

    provider.add_span_processor(processor)
    # ``set_tracer_provider`` is one-shot per process; we attempt it but
    # don't depend on the global because tests reset+reconfigure many
    # times in the same process. We always pull the tracer directly
    # from the provider we just built.
    with suppress(Exception):  # guarded against "already set" in re-init
        trace.set_tracer_provider(provider)
    _PROVIDER = provider

    # Swap the shim's tracer attribute to our wrapper so the existing
    # pipeline call sites start emitting real spans without code edits.
    # We bind to ``provider.get_tracer`` (instance method) rather than
    # the global ``trace.get_tracer`` so re-configuration in tests is
    # honoured even when the global provider is frozen.
    from voicesaju import tracing as _tracing_shim

    _tracing_shim.tracer = _OTelTracerWrapper(provider.get_tracer(service_name))

    return True


def instrument_app(app: FastAPI) -> None:
    """Wire FastAPI + httpx auto-instrumentation onto an app instance.

    Idempotent — repeated calls (e.g. in tests) are safe because the
    instrumentors check internal state before re-wrapping.
    """
    FastAPIInstrumentor.instrument_app(app)
    HTTPXClientInstrumentor().instrument()


# ---------------------------------------------------------------------------
# /metrics route — Prometheus exposition format.
# ---------------------------------------------------------------------------


async def metrics_route(_request: Request) -> Response:
    """Return the Prometheus exposition format for ``METRICS_REGISTRY``."""
    payload = generate_latest(METRICS_REGISTRY)
    return Response(content=payload, media_type=CONTENT_TYPE_LATEST)


def attach_metrics_route(app: FastAPI) -> None:
    """Mount ``GET /metrics`` on the given app."""
    app.add_api_route(
        "/metrics",
        metrics_route,
        methods=["GET"],
        tags=["meta"],
        include_in_schema=False,
    )


def get_in_memory_exporter() -> InMemorySpanExporter | None:
    """Return the in-memory exporter when ``use_in_memory_exporter=True``.

    Test helper — production callers should not depend on this.
    """
    return _IN_MEMORY_EXPORTER


def reset_for_tests() -> None:
    """Reset module state so a new ``configure_otel`` can run cleanly."""
    global _PROVIDER, _IN_MEMORY_EXPORTER

    if _IN_MEMORY_EXPORTER is not None:
        _IN_MEMORY_EXPORTER.clear()
        _IN_MEMORY_EXPORTER = None
    _PROVIDER = None
    # Restore the legacy no-op tracer so subsequent tests start clean.
    from voicesaju import tracing as _tracing_shim

    _tracing_shim.tracer = _tracing_shim._NoopTracer()


__all__ = [
    "LLM_CALL_DURATION_SECONDS",
    "METRICS_REGISTRY",
    "READING_PIPELINE_E2E_SECONDS",
    "TTS_FIRST_CHUNK_SECONDS",
    "attach_metrics_route",
    "configure_otel",
    "get_in_memory_exporter",
    "instrument_app",
    "metrics_route",
    "reset_for_tests",
]
