"""seed tone_eval_cases from tests/fixtures/tone_evalset.json

Implements ISSUE-019 (FR-032 layer-2 release gate). Reads the
``tests/fixtures/tone_evalset.json`` fixture (≥ 50 labelled cases) and
seeds it into ``tone_eval_cases`` so the offline eval pipeline (and the
ISSUE-020 deny-list regression) can replay the same dataset against new
prompt versions and guardrail revisions.

The seed payload is intentionally **content-only** — ``id`` and
``created_at`` are left to the column defaults so the migration is
deterministic across SQLite (used by unit tests) and Postgres (CI +
prod).

Idempotency strategy:

- **Postgres**: ``ON CONFLICT (input_text) DO NOTHING`` against the
  partial unique index ``tone_eval_cases_input_text_uq`` created by this
  same migration (Postgres-only).
- **SQLite** (unit tests): the migration ``upgrade()`` runs once per
  in-memory engine, so a guard check (``SELECT 1 FROM tone_eval_cases
  LIMIT 1``) is sufficient — duplicate inserts only happen if the test
  harness calls ``upgrade()`` twice, which it never does.

Revision ID: 0011_seed_tone_eval_cases
Revises: 0010_tone_tables
Create Date: 2026-05-29
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "0011_seed_tone_eval_cases"
down_revision = "0010_tone_tables"
branch_labels = None
depends_on = None


# Resolve fixture relative to this migration file so the seed works
# regardless of CWD (alembic CLI vs. importlib-loaded unit tests).
_FIXTURE_PATH = (
    Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "tone_evalset.json"
)


def _is_postgres() -> bool:
    return op.get_bind().dialect.name == "postgresql"


def _load_fixture() -> list[dict]:
    """Load the tone evalset fixture. Returns the list of cases."""
    with _FIXTURE_PATH.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def upgrade() -> None:
    cases = _load_fixture()

    # Postgres-only: partial unique on input_text so reruns are
    # idempotent and editorial updates can replace the same row.
    if _is_postgres():
        op.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS "
            "tone_eval_cases_input_text_uq "
            "ON tone_eval_cases (input_text)"
        )

    bind = op.get_bind()
    table = sa.table(
        "tone_eval_cases",
        sa.column("id", sa.String(length=36)),
        sa.column("case_kind", sa.String()),
        sa.column("input_text", sa.Text()),
        sa.column("expected_label", sa.String()),
        sa.column("category_tag", sa.String()),
    )

    if _is_postgres():
        # Use raw SQL with ON CONFLICT for idempotent reruns. SQLAlchemy
        # core's `insert(table).on_conflict_do_nothing` requires the
        # postgres dialect import which would force this whole migration
        # to import dialect-specific code at module load.
        for case in cases:
            bind.execute(
                sa.text(
                    "INSERT INTO tone_eval_cases "
                    "(id, case_kind, input_text, expected_label, category_tag) "
                    "VALUES (:id, :case_kind, :input_text, :expected_label, "
                    ":category_tag) "
                    "ON CONFLICT (input_text) DO NOTHING"
                ),
                {
                    "id": str(uuid.uuid4()),
                    "case_kind": case["case_kind"],
                    "input_text": case["input_text"],
                    "expected_label": case["expected_label"],
                    "category_tag": case["category_tag"],
                },
            )
    else:
        # SQLite path: guard against duplicate seeds (e.g. when the
        # migration runs against an already-seeded test DB) by checking
        # for existing rows first.
        existing = bind.execute(
            sa.text("SELECT COUNT(*) FROM tone_eval_cases")
        ).scalar_one()
        if existing > 0:
            return
        op.bulk_insert(
            table,
            [
                {
                    "id": str(uuid.uuid4()),
                    "case_kind": case["case_kind"],
                    "input_text": case["input_text"],
                    "expected_label": case["expected_label"],
                    "category_tag": case["category_tag"],
                }
                for case in cases
            ],
        )


def downgrade() -> None:
    # Restoring the deleted rows is impractical for editorial fixtures
    # (the seed comes from a JSON file checked into source), so we just
    # truncate the table — re-running ``upgrade`` repopulates it.
    op.execute("DELETE FROM tone_eval_cases")

    if _is_postgres():
        op.execute("DROP INDEX IF EXISTS tone_eval_cases_input_text_uq")
