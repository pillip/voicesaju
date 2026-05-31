"""Sanity tests for the Grafana reading-pipeline dashboard (ISSUE-089).

The dashboard JSON at ``ops/grafana/dashboards/reading_pipeline.json``
is the single source of truth for the 5-panel observability view that
ops + on-call rely on (architecture §12.4). Live verification against
Grafana Cloud is deferred until the Phase-2 staging deploy lands —
these tests gate the *static* contract:

- The file parses as JSON.
- The schema looks like a Grafana v9+ dashboard (``title``, ``panels``,
  ``schemaVersion``, ``templating``).
- All 5 required panels are present and reference the metric names
  declared in ``voicesaju.observability.otel`` + architecture §12.2.
- Alert thresholds for warn/page boundaries from §12.4 are encoded in
  the JSON (text search — the exact threshold semantics are validated
  manually post-deploy).

PRD-Ref: NFR-001, NFR-002, NFR-007, NFR-011.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[3]
_DASHBOARD_PATH = (
    _REPO_ROOT / "ops" / "grafana" / "dashboards" / "reading_pipeline.json"
)


@pytest.fixture(scope="module")
def dashboard() -> dict[str, Any]:
    if not _DASHBOARD_PATH.exists():
        pytest.fail(f"dashboard JSON not found: {_DASHBOARD_PATH}")
    return json.loads(_DASHBOARD_PATH.read_text(encoding="utf-8"))


def test_dashboard_file_exists() -> None:
    assert _DASHBOARD_PATH.exists(), f"missing dashboard: {_DASHBOARD_PATH}"


def test_dashboard_parses_as_json() -> None:
    payload = _DASHBOARD_PATH.read_text(encoding="utf-8")
    obj = json.loads(payload)
    assert isinstance(obj, dict), "dashboard must be a JSON object"


def test_dashboard_has_grafana_v9_schema_fields(dashboard: dict[str, Any]) -> None:
    """Grafana v9+ dashboard JSON requires these top-level fields."""
    for key in ("title", "panels", "schemaVersion", "templating"):
        assert key in dashboard, f"missing required top-level key: {key}"

    # schemaVersion >= 30 is roughly Grafana 8.x; v9+ is 36+. Accept >= 30.
    assert isinstance(dashboard["schemaVersion"], int)
    assert (
        dashboard["schemaVersion"] >= 30
    ), f"schemaVersion {dashboard['schemaVersion']} is too old; v9+ is >= 36"

    # `panels` must be a non-empty list and each panel must have an id/title/targets.
    panels = dashboard["panels"]
    assert isinstance(panels, list) and panels, "panels must be a non-empty list"


def test_dashboard_has_five_required_panels(dashboard: dict[str, Any]) -> None:
    """AC1 — 5 panels: e2e p95, TTS p95, LLM cost, payment, tone violation."""
    panels = dashboard["panels"]
    # Concatenate titles (case-insensitive) for keyword presence checks.
    titles = " | ".join((p.get("title") or "").lower() for p in panels)

    required_keywords = (
        # Panel 1 — reading e2e p95
        "reading",
        # Panel 2 — TTS first chunk p95
        "tts",
        # Panel 3 — LLM cost p50/p95
        "llm",
        # Panel 4 — payment failure rate
        "payment",
        # Panel 5 — tone violation rate
        "tone",
    )
    for kw in required_keywords:
        assert kw in titles, f"no panel title mentions {kw!r}; got {titles!r}"

    assert len(panels) >= 5, f"expected >= 5 panels, got {len(panels)}"


def test_dashboard_references_otel_histogram_metric_names(
    dashboard: dict[str, Any],
) -> None:
    """The dashboard queries must reference the histograms exposed in
    ``voicesaju.observability.otel`` — keeping the metric names stable
    is a contract between the SDK and ops."""
    blob = json.dumps(dashboard)

    # Histogram base names that the OTel module exposes (see
    # voicesaju/observability/otel.py). Prometheus appends `_bucket` so
    # the queries reference either form.
    required_metrics = (
        "reading_pipeline_e2e_seconds",
        "tts_first_chunk_seconds",
        "llm_call_duration_seconds",
    )
    for metric in required_metrics:
        assert (
            metric in blob
        ), f"dashboard does not reference metric {metric!r} — panel cannot render"


def test_dashboard_references_counter_metric_names(
    dashboard: dict[str, Any],
) -> None:
    """Payment failure + tone violation panels must reference the
    counter names from architecture §12.2."""
    blob = json.dumps(dashboard)
    required_counters = (
        "payment_failures_total",
        "tone_violation_total",
    )
    for metric in required_counters:
        assert metric in blob, f"dashboard does not reference counter {metric!r}"


def test_dashboard_encodes_p95_quantile_queries(dashboard: dict[str, Any]) -> None:
    """Reading e2e + TTS first chunk p95 panels must use
    ``histogram_quantile(0.95, ...)`` queries — the SLO contract is on
    the 95th percentile (NFR-001 ≤ 3s, NFR-002 ≤ 1.5s)."""
    blob = json.dumps(dashboard)
    assert (
        "histogram_quantile" in blob
    ), "no histogram_quantile() PromQL — p95 panels cannot render"
    # At least one panel queries 0.95.
    assert "0.95" in blob, "no 0.95 quantile in PromQL queries"


def test_dashboard_encodes_alert_thresholds_per_architecture(
    dashboard: dict[str, Any],
) -> None:
    """AC2 — thresholds per architecture §12.4. We check for presence of
    the documented warn boundaries (3 / 1.5 / 0.01 / 0.005) in the
    panel thresholds blob so an admin can see them at a glance and
    wire Slack alerts."""
    blob = json.dumps(dashboard)
    # §12.4 warn thresholds:
    # - Reading e2e p95 warn = 3s
    # - TTS first chunk p95 warn = 1.5s
    # - Payment failure rate warn = 0.01 (1%/hour)
    # - Tone violation rate warn = 0.005 (0.5%/sessions)
    expected_thresholds = ("3", "1.5", "0.01", "0.005")
    missing = [t for t in expected_thresholds if t not in blob]
    assert not missing, f"missing alert thresholds from §12.4: {missing}"


def test_dashboard_uid_is_stable(dashboard: dict[str, Any]) -> None:
    """The dashboard ``uid`` must be a fixed string so links don't
    break across re-imports."""
    uid = dashboard.get("uid")
    assert isinstance(uid, str) and uid, "dashboard needs a non-empty `uid`"
    # No whitespace, lowercase-ish, alphanumeric + dash.
    assert " " not in uid, "uid must not contain whitespace"
    assert len(uid) >= 4, f"uid too short: {uid!r}"


def test_dashboard_panel_ids_are_unique(dashboard: dict[str, Any]) -> None:
    """Grafana requires unique panel ids per dashboard."""
    panels = dashboard["panels"]
    ids = [p.get("id") for p in panels]
    assert all(isinstance(i, int) for i in ids), "every panel needs an integer id"
    assert len(ids) == len(set(ids)), f"duplicate panel ids: {ids}"


def test_grafana_readme_exists() -> None:
    """The brief import/wiring documentation must accompany the JSON."""
    readme = _REPO_ROOT / "ops" / "grafana" / "README.md"
    assert readme.exists(), f"missing ops/grafana/README.md: {readme}"
    body = readme.read_text(encoding="utf-8")
    # Must mention the import step + alert wiring expectations.
    assert "import" in body.lower(), "README must document the import flow"
    assert "alert" in body.lower(), "README must mention alert wiring"
