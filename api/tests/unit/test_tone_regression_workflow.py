"""Sanity tests for the tone_regression CI workflow (ISSUE-090).

These tests do not execute the workflow — they verify that the YAML
file at ``.github/workflows/tone_regression.yml`` exists, parses as
valid YAML, and contains the structural elements required by AC1/AC2:

- Runs on ``pull_request`` AND ``push`` to ``main`` (AC1).
- Invokes the ``tone_regression``-marked tests in
  ``api/tests/regression/test_tone_evalset.py`` (AC2 — coverage of the
  deny-list gate).
- ``working-directory: api`` so ``uv`` resolves the project.

When the workflow's pytest step fails on a real CI run (because the
deny-list missed a violation case), GitHub's required-status check
blocks the PR merge. That gating step is configured in the GitHub UI
(admin-only) — this test asserts the workflow itself is wired
correctly.

PRD-Ref: FR-032.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

# Path to the workflow at repo root.
_REPO_ROOT = Path(__file__).resolve().parents[3]
_WORKFLOW_PATH = _REPO_ROOT / ".github" / "workflows" / "tone_regression.yml"


@pytest.fixture(scope="module")
def workflow() -> dict:
    if not _WORKFLOW_PATH.exists():
        pytest.fail(f"workflow file not found: {_WORKFLOW_PATH}")
    return yaml.safe_load(_WORKFLOW_PATH.read_text(encoding="utf-8"))


def test_workflow_file_exists() -> None:
    assert _WORKFLOW_PATH.exists(), f"missing workflow: {_WORKFLOW_PATH}"


def test_workflow_is_valid_yaml(workflow: dict) -> None:
    # Parsing into a non-empty dict is the contract.
    assert isinstance(workflow, dict) and workflow, "workflow YAML is empty"
    assert "name" in workflow, "workflow needs a name"


def test_workflow_triggers_on_pull_request_and_main_push(workflow: dict) -> None:
    """AC1 — every PR + every push to main runs the tone regression."""
    # PyYAML maps the ``on`` key to literal True because ``on`` is a YAML
    # boolean. Handle both spellings for robustness.
    on = workflow.get("on") or workflow.get(True)
    assert on, "workflow has no `on:` triggers"

    assert "pull_request" in on, "must trigger on pull_request"
    pr_cfg = on["pull_request"]
    assert (
        pr_cfg is None or "branches" in pr_cfg
    ), "pull_request trigger should be open or scoped via branches"

    assert "push" in on, "must trigger on push"
    push_cfg = on["push"]
    assert push_cfg and "main" in push_cfg.get(
        "branches", []
    ), "push trigger must include main branch"


def test_workflow_runs_tone_regression_pytest(workflow: dict) -> None:
    """AC2 — the workflow must execute the marker that gates the deny-list."""
    jobs = workflow.get("jobs", {})
    assert jobs, "workflow has no jobs"

    # Collect all run commands across all jobs/steps.
    run_commands: list[str] = []
    for job in jobs.values():
        for step in job.get("steps", []):
            cmd = step.get("run")
            if cmd:
                run_commands.append(cmd)

    blob = "\n".join(run_commands)
    # The deny-list gate is gated by the ``tone_regression`` pytest marker.
    assert (
        "-m tone_regression" in blob or "-m 'tone_regression'" in blob
    ), "no `pytest -m tone_regression` invocation found"
    # The marked tests live in this file.
    assert (
        "tests/regression/test_tone_evalset.py" in blob
    ), "must target tests/regression/test_tone_evalset.py"


def test_workflow_uses_uv_in_api_dir(workflow: dict) -> None:
    """Project convention: backend tests run via ``uv run pytest`` from ``api/``."""
    jobs = workflow.get("jobs", {})
    assert jobs, "workflow has no jobs"

    # At least one job must scope ``working-directory: api``.
    has_api_dir = False
    has_uv = False
    has_setup_uv = False
    for job in jobs.values():
        defaults = job.get("defaults", {}) or {}
        run_defaults = defaults.get("run", {}) or {}
        if run_defaults.get("working-directory") == "api":
            has_api_dir = True
        for step in job.get("steps", []):
            run = step.get("run", "") or ""
            uses = step.get("uses", "") or ""
            if "uv run pytest" in run:
                has_uv = True
            if "astral-sh/setup-uv" in uses:
                has_setup_uv = True

    assert has_api_dir, "no job sets `working-directory: api`"
    assert has_uv, "no step runs `uv run pytest`"
    assert has_setup_uv, "no step installs uv via astral-sh/setup-uv"


def test_workflow_required_check_documented(workflow: dict) -> None:
    """AC notes — the GitHub required-status configuration is admin-only.

    The workflow name must be stable so admins can mark it as a required
    check on the protected branch. We assert it does not include
    version numbers or environment suffixes that would churn.
    """
    name = workflow["name"]
    assert "tone" in name.lower(), f"workflow name should mention `tone`: {name!r}"
    # Stable, snake-cased-or-spaced label — no dates/versions.
    forbidden = ("v1", "v2", "2026", "2025", "staging", "prod")
    for token in forbidden:
        assert token not in name.lower(), (
            f"workflow name must be stable for required-check pinning "
            f"(found unstable token {token!r} in {name!r})"
        )
