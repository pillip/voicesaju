"""Unit tests for User and Device models.

Verifies that the SQLAlchemy declarative models import cleanly, expose every
column documented in `docs/data_model.md` §4.2 and §4.4, and are registered
on the shared `Base.metadata`. Postgres-specific behaviour (partial unique
indexes, CHECK on multiple provider columns, raw-SQL DDL) is exercised in
`tests/integration/db/test_users_constraints.py` against a real Postgres
instance.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
from sqlalchemy import inspect

from voicesaju.db.base import Base
from voicesaju.db.models import Device, User

API_DIR = Path(__file__).resolve().parents[3]
MIGRATION_PATH = API_DIR / "alembic" / "versions" / "0003_users_devices.py"


def _load_migration_module():
    spec = importlib.util.spec_from_file_location(
        "migration_0003_users_devices", MIGRATION_PATH
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_user_model_has_expected_columns() -> None:
    cols = {c.name for c in inspect(User).columns}
    expected = {
        "id",
        "kakao_sub",
        "apple_sub",
        "toss_id",
        "email_hash",
        "display_locale",
        "created_at",
        "updated_at",
        "last_seen_at",
        "deleted_at",
    }
    missing = expected - cols
    assert not missing, f"User missing columns: {missing}"


def test_user_table_metadata_registered() -> None:
    assert "users" in Base.metadata.tables
    table = Base.metadata.tables["users"]
    assert table.primary_key is not None
    pk_cols = {c.name for c in table.primary_key.columns}
    assert pk_cols == {"id"}


def test_device_model_has_expected_columns() -> None:
    cols = {c.name for c in inspect(Device).columns}
    expected = {
        "id",
        "device_id_client",
        "linked_user_id",
        "first_seen_at",
        "last_seen_at",
        "user_agent_hash",
    }
    missing = expected - cols
    assert not missing, f"Device missing columns: {missing}"


def test_device_table_metadata_registered() -> None:
    assert "devices" in Base.metadata.tables
    table = Base.metadata.tables["devices"]
    pk_cols = {c.name for c in table.primary_key.columns}
    assert pk_cols == {"id"}


def test_device_client_id_is_unique() -> None:
    table = Base.metadata.tables["devices"]
    client_col = table.c.device_id_client
    assert client_col.unique is True, "device_id_client must carry a unique constraint"


def test_device_has_fk_to_users() -> None:
    table = Base.metadata.tables["devices"]
    linked_col = table.c.linked_user_id
    fk_targets = [fk.target_fullname for fk in linked_col.foreign_keys]
    assert any(
        target.endswith("users.id") for target in fk_targets
    ), f"linked_user_id FK targets: {fk_targets}"


def test_migration_revision_chain() -> None:
    module = _load_migration_module()
    assert module.revision == "0003_users_devices"
    assert module.down_revision == "0002_postgres_enums"


def test_migration_declares_users_and_devices_tables() -> None:
    """Smoke-check: the migration's upgrade() source mentions both tables."""
    src = MIGRATION_PATH.read_text(encoding="utf-8")
    assert "create_table" in src
    assert '"users"' in src or "'users'" in src
    assert '"devices"' in src or "'devices'" in src


def test_uuidv7_helper_importable() -> None:
    """The model module exposes a `uuid7` callable used for PK defaults."""
    from voicesaju.db.models import users as users_module

    assert callable(users_module.uuid7)
    value = users_module.uuid7()
    # Both real uuidv7 and the uuid.uuid4 fallback return 16-byte UUIDs
    assert hasattr(value, "bytes")
    assert len(value.bytes) == 16


@pytest.mark.parametrize(
    "ddl_phrase",
    [
        "users_kakao_sub_uq",
        "users_apple_sub_uq",
        "users_toss_id_uq",
        "users_email_hash_idx",
        "users_deleted_at_idx",
        "devices_client_uq",
        "devices_linked_user_idx",
    ],
)
def test_migration_declares_expected_indexes(ddl_phrase: str) -> None:
    src = MIGRATION_PATH.read_text(encoding="utf-8")
    assert ddl_phrase in src, f"migration missing index/DDL phrase: {ddl_phrase}"


def test_migration_declares_check_constraint() -> None:
    src = MIGRATION_PATH.read_text(encoding="utf-8")
    # CHECK must require ≥1 of kakao_sub / apple_sub / toss_id
    assert "kakao_sub IS NOT NULL" in src
    assert "apple_sub IS NOT NULL" in src
    assert "toss_id IS NOT NULL" in src
