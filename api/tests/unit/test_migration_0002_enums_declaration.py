"""Unit-level structural test for migration 0002_postgres_enums.

Runs in default CI (no Postgres required). Asserts that the migration
declares exactly the 13 enums from `docs/data_model.md` §4.1 with the
expected names and values, so a drift in the migration is caught even
without a Postgres-backed integration run.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

API_DIR = Path(__file__).resolve().parents[2]
MIGRATION_PATH = API_DIR / "alembic" / "versions" / "0002_postgres_enums.py"


def _load_migration_module():
    spec = importlib.util.spec_from_file_location(
        "migration_0002_postgres_enums", MIGRATION_PATH
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


EXPECTED: dict[str, tuple[str, ...]] = {
    "gender_enum": ("F", "M"),
    "category_enum": ("love", "work", "money"),
    "reading_status_enum": (
        "queued",
        "streaming",
        "done",
        "failed",
        "refunded",
        "cancelled",
    ),
    "tarot_status_enum": ("streaming", "done", "failed"),
    "payment_type_enum": (
        "single",
        "subscription_initial",
        "subscription_recurring",
    ),
    "payment_method_enum": ("tosspay", "kakaopay"),
    "payment_status_enum": (
        "pending",
        "paid",
        "failed",
        "refunded",
        "partially_refunded",
    ),
    "subscription_status_enum": (
        "active",
        "cancel_at_period_end",
        "cancelled",
        "past_due",
    ),
    "free_token_kind_enum": (
        "nonmember_trial",
        "signup_grant",
        "failure_compensation",
        "ops_grant",
    ),
    "auth_provider_enum": ("kakao", "apple", "toss"),
    "character_key_enum": ("nuna", "dosa"),
    "tone_eval_label_enum": ("ok", "violation"),
    "audit_action_enum": (
        "profile_read",
        "profile_update",
        "soft_delete",
        "hard_delete",
        "payment_refund",
        "correction_used",
        "export_data",
    ),
}


def test_migration_declares_thirteen_enums() -> None:
    module = _load_migration_module()
    declared = dict(module.ENUMS)
    assert len(declared) == 13
    assert set(declared.keys()) == set(EXPECTED.keys())


def test_migration_values_match_data_model() -> None:
    module = _load_migration_module()
    declared = dict(module.ENUMS)
    for name, values in EXPECTED.items():
        assert (
            declared[name] == values
        ), f"enum {name} values drifted from data_model.md §4.1"


def test_migration_revision_chain() -> None:
    module = _load_migration_module()
    assert module.revision == "0002_postgres_enums"
    assert module.down_revision == "0001_initial"
