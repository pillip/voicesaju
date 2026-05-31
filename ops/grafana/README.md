# Grafana — VoiceSaju observability

This directory holds the Grafana dashboards committed to the repo so
panel queries + alert thresholds are reviewable in PRs and importable
into any Grafana instance (Cloud or self-hosted).

PRD-Ref: NFR-001, NFR-002, NFR-007, NFR-009, NFR-010, NFR-011.
Architecture refs: §12.2 (metric catalog), §12.4 (alert thresholds).

## Dashboards

- `dashboards/reading_pipeline.json` — primary reading-pipeline SLO
  dashboard with 5 panels:
  1. Reading e2e p95 (target NFR-001 ≤ 3s).
  2. TTS first chunk p95 (target NFR-002 ≤ 1.5s).
  3. LLM call duration p50/p95 by model (cost proxy, NFR-007).
  4. Payment failure rate per hour (NFR-009 ≤ 2%).
  5. Tone violation rate per session (NFR-010 ≤ 1%).

  UID: `voicesaju-reading-pipeline`. Stable across re-imports — admin
  may pin Slack alert rules to this UID.

## Importing into Grafana Cloud

1. Open Grafana → `Dashboards` → `New` → `Import`.
2. Upload `dashboards/reading_pipeline.json` (or paste the JSON).
3. Select the Prometheus datasource configured against the backend
   `/metrics` endpoint (scrape job: `voicesaju-api`).
4. Click `Import`. The 5 panels render against live metrics.

> Live verification (panel data renders + Slack alert fires) is
> deferred until the Phase-2 staging deploy (ISSUE-084 + ISSUE-085)
> lands. Until then the JSON ships as the agreed source of truth.

## Alert wiring (Slack)

Each panel embeds an `alert` block following architecture §12.4
thresholds:

| Panel | Warn | Page |
|-------|------|------|
| Reading e2e p95 | > 3s for 5 min | > 5s for 5 min |
| TTS first chunk p95 | > 1.5s for 5 min | > 3s for 5 min |
| Payment failure rate | > 1% per hour | > 2% per hour |
| LLM cost p50/p95 | manual review (cost-band) | — |
| Tone violation rate | > 0.5% of sessions | > 1% of sessions |

To enable Slack notifications:
1. In Grafana → `Alerting` → `Contact points` → create a `Slack`
   contact pointing at the `#voicesaju-alerts` webhook.
2. In `Notification policies`, route the dashboard's alert rules to
   the Slack contact (default policy is fine for v1).
3. Open each panel → `Alert` tab → confirm the threshold + `for`
   duration match the table above.

`page`-level breaches should additionally page on-call via the
PagerDuty integration (configure under `Notification policies` once
the rotation is set up post-launch).

## Required Prometheus metrics

The dashboard expects the following metrics from
`voicesaju.observability.otel` (already exposed via `/metrics`
after ISSUE-077):

- `reading_pipeline_e2e_seconds_bucket` — histogram.
- `tts_first_chunk_seconds_bucket` — histogram.
- `llm_call_duration_seconds_bucket{model, kind}` — histogram.

Counters used by panels 4 + 5 (`payment_failures_total`,
`payment_attempts_total`, `tone_violation_total`) are catalogued in
architecture §12.2 but not yet emitted from the SDK — wiring those
counters is tracked as a follow-up. Panels 4 + 5 will render `No
data` until then, which is the correct behaviour (the dashboard
JSON itself is the deliverable for ISSUE-089).

## Rollback

`Dashboards` → open `VoiceSaju — Reading Pipeline` → `…` → `Delete`.
Re-import from this directory to restore.
