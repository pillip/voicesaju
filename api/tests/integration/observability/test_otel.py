"""Integration tests for OTel + /metrics (ISSUE-077).

Covers:

1. ``GET /metrics`` returns 200 with Prometheus exposition format that
   contains the three required histograms.
2. ``configure_otel(enabled=True, use_in_memory_exporter=True)`` plus
   the legacy tracer-shim swap → a span created via
   ``voicesaju.tracing.tracer`` ends up in the in-memory exporter.
3. ``configure_otel(enabled=False)`` is a no-op (returns False) so the
   legacy no-op tracer keeps delivering.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from voicesaju.observability.otel import (
    LLM_CALL_DURATION_SECONDS,
    READING_PIPELINE_E2E_SECONDS,
    TTS_FIRST_CHUNK_SECONDS,
    configure_otel,
    get_in_memory_exporter,
    reset_for_tests,
)


@pytest.fixture
def client() -> TestClient:
    from voicesaju.main import create_app

    app = create_app()
    return TestClient(app)


@pytest.fixture(autouse=True)
def _cleanup_otel() -> None:
    yield
    reset_for_tests()


def test_metrics_endpoint_returns_prometheus_format(client: TestClient) -> None:
    # Seed each histogram so its `_count` / `_bucket` lines exist.
    READING_PIPELINE_E2E_SECONDS.observe(1.5)
    TTS_FIRST_CHUNK_SECONDS.observe(0.8)
    LLM_CALL_DURATION_SECONDS.labels(model="claude-haiku", kind="stream").observe(2.0)

    response = client.get("/metrics")

    assert response.status_code == 200
    body = response.text
    # Content-type is the Prometheus exposition v0.0.4 / OpenMetrics shape.
    assert "text/plain" in response.headers["content-type"]
    # All three required histograms are present.
    assert "reading_pipeline_e2e_seconds" in body
    assert "tts_first_chunk_seconds" in body
    assert "llm_call_duration_seconds" in body
    # And the histogram-shape lines exist.
    assert "reading_pipeline_e2e_seconds_bucket" in body
    assert "tts_first_chunk_seconds_bucket" in body
    assert "llm_call_duration_seconds_bucket" in body


def test_metrics_endpoint_present_when_otel_disabled(client: TestClient) -> None:
    """Even with OTEL_ENABLED=false, /metrics must be reachable.

    The Prometheus endpoint is independent from OTel tracing; Grafana
    Cloud scrapes it regardless.
    """
    response = client.get("/metrics")
    assert response.status_code == 200


def test_configure_otel_disabled_is_noop() -> None:
    result = configure_otel(enabled=False, endpoint=None)
    assert result is False


def test_configure_otel_swaps_legacy_tracer_to_real_sdk() -> None:
    # Enable with the in-memory exporter so we can assert on captured spans.
    result = configure_otel(
        enabled=True,
        endpoint=None,
        use_in_memory_exporter=True,
    )
    assert result is True

    # Now call the legacy shim's start_span — it MUST emit through the
    # OTel pipeline because configure_otel swapped voicesaju.tracing.tracer.
    from voicesaju.tracing import tracer

    with tracer.start_span("pipeline.test_span") as span:
        span.set_attribute("reading_id", "rd_test_001")
        span.set_attribute("category", "love")

    exporter = get_in_memory_exporter()
    assert exporter is not None
    spans = exporter.get_finished_spans()

    # Exactly one span captured, with the expected name + attributes.
    assert len(spans) == 1
    assert spans[0].name == "pipeline.test_span"
    attrs = dict(spans[0].attributes or {})
    assert attrs["reading_id"] == "rd_test_001"
    assert attrs["category"] == "love"


def test_configure_otel_records_multiple_pipeline_spans() -> None:
    configure_otel(
        enabled=True,
        endpoint=None,
        use_in_memory_exporter=True,
    )
    from voicesaju.tracing import tracer

    span_names = [
        "pipeline.chart_lookup",
        "pipeline.llm_stream",
        "pipeline.guardrail",
        "pipeline.tts_stream",
        "pipeline.r2_upload",
        "pipeline.sse_emit_end",
    ]
    for name in span_names:
        with tracer.start_span(name) as span:
            span.set_attribute("step", name)

    exporter = get_in_memory_exporter()
    captured = sorted(s.name for s in exporter.get_finished_spans())
    assert captured == sorted(span_names)
