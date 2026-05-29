"""Unit tests for Profile model — envelope roundtrip + correction bounds.

Verifies that:
- The SQLAlchemy declarative model imports cleanly and exposes every column
  documented in `docs/data_model.md` §4.5.
- The `birth_dt` property encrypts on write (no plaintext leaks into the
  `birth_dt_enc` JSONB) and decrypts on read.
- The CHECK constraint on `correction_count` rejects values outside [0,2]
  on SQLite (the migration also emits a Postgres-level version).
- The migration revision chain stays valid.
"""

from __future__ import annotations

import base64
import importlib.util
import json
import uuid
from pathlib import Path

import pytest
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.ext.asyncio import async_sessionmaker as _async_sessionmaker

from voicesaju.db.base import Base
from voicesaju.db.models import Profile, SajuChart, User


@pytest.fixture(autouse=True)
def _local_kek_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure `get_kms_provider()` can resolve a deterministic LocalKMS.

    The envelope helpers call `get_kms_provider()` on each encrypt/decrypt;
    that helper reads `LOCAL_KEK_BASE64` from the environment. We inject a
    fixed-but-non-placeholder KEK so the encryption pipeline works without
    requiring CI to provision one.
    """
    fake_kek = base64.b64encode(b"\x00" * 32).decode("ascii")
    monkeypatch.setenv("LOCAL_KEK_BASE64", fake_kek)
    monkeypatch.setenv("KMS_PROVIDER", "local")


API_DIR = Path(__file__).resolve().parents[3]
MIGRATION_PATH = API_DIR / "alembic" / "versions" / "0004_profiles_saju_charts.py"


def _load_migration_module():
    spec = importlib.util.spec_from_file_location(
        "migration_0004_profiles_saju_charts", MIGRATION_PATH
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_profile_model_has_expected_columns() -> None:
    cols = {c.name for c in inspect(Profile).columns}
    expected = {
        "id",
        "user_id",
        "birth_dt_enc",
        "birth_is_lunar",
        "birth_time_known",
        "name_optional",
        "correction_count",
        "created_at",
        "updated_at",
        "deleted_at",
    }
    missing = expected - cols
    assert not missing, f"Profile missing columns: {missing}"


def test_profile_table_metadata_registered() -> None:
    assert "profiles" in Base.metadata.tables
    table = Base.metadata.tables["profiles"]
    pk_cols = {c.name for c in table.primary_key.columns}
    assert pk_cols == {"id"}


def test_profile_user_id_is_unique() -> None:
    table = Base.metadata.tables["profiles"]
    user_col = table.c.user_id
    assert user_col.unique is True, "profiles.user_id must be unique (1:1)"


def test_profile_has_fk_to_users() -> None:
    table = Base.metadata.tables["profiles"]
    user_col = table.c.user_id
    targets = [fk.target_fullname for fk in user_col.foreign_keys]
    assert any(t.endswith("users.id") for t in targets)


def test_birth_dt_encrypt_decrypt_roundtrip() -> None:
    """Setting `profile.birth_dt` stores an envelope; reading decrypts it.

    The `_local_kek_env` fixture installs `LOCAL_KEK_BASE64` so the default
    `get_kms_provider()` returns a working `LocalKMS` — no monkeypatching
    of the envelope module is required.
    """
    user_id = uuid.uuid4()
    profile = Profile(user_id=user_id, birth_dt="2000-01-01T07:30Z")
    assert profile.birth_dt_enc is not None
    # 7 envelope keys per data_model §4.25
    assert set(profile.birth_dt_enc.keys()) == {
        "kek_version",
        "wrapped_dek",
        "iv",
        "ciphertext",
        "tag",
        "algorithm",
        "aad",
    }
    # No plaintext leakage into the JSONB blob.
    blob = json.dumps(profile.birth_dt_enc)
    assert "2000" not in blob
    assert "07:30" not in blob

    # Roundtrip — read back the plaintext.
    assert profile.birth_dt == "2000-01-01T07:30Z"


def test_birth_dt_requires_user_id_on_set() -> None:
    p = Profile()
    with pytest.raises(ValueError, match="user_id"):
        p.birth_dt = "2000-01-01T00:00Z"


def test_birth_dt_returns_none_when_envelope_unset() -> None:
    """A Profile whose JSONB column was never written reads as None.

    Allocate an instance without going through `__init__` (we skip the
    automatic encrypt) and set `birth_dt_enc` directly to an empty dict;
    the `birth_dt` getter must treat falsy envelopes as "no value yet".
    """
    p = Profile(user_id=uuid.uuid4())
    # Simulate a row that has never had birth_dt assigned: empty dict.
    p.birth_dt_enc = {}  # type: ignore[assignment]
    assert p.birth_dt is None


@pytest.mark.asyncio
async def test_correction_count_check_constraint_enforced_on_sqlite() -> None:
    """SQLite honors application-level CHECK constraints from the model."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    try:
        # Enable foreign keys + check constraints on SQLite.
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        session_factory = _async_sessionmaker(
            bind=engine, expire_on_commit=False, class_=AsyncSession
        )

        # Use explicit string UUIDs so aiosqlite (which has no native UUID
        # binding) can persist them. Postgres production code stores UUIDs
        # via asyncpg which has full UUID support.
        async with session_factory() as session:
            u1_id = str(uuid.uuid4())
            user = User(id=u1_id, kakao_sub="kakao:test-1")
            session.add(user)
            await session.flush()

            # Valid: correction_count=2 is the upper bound.
            p_ok = Profile(
                id=str(uuid.uuid4()),
                user_id=u1_id,
                birth_dt="1990-05-15T10:00Z",
                correction_count=2,
            )
            session.add(p_ok)
            await session.commit()

        # Invalid: correction_count=3 must violate the CHECK.
        async with session_factory() as session:
            u2_id = str(uuid.uuid4())
            user2 = User(id=u2_id, kakao_sub="kakao:test-2")
            session.add(user2)
            await session.flush()

            p_bad = Profile(
                id=str(uuid.uuid4()),
                user_id=u2_id,
                birth_dt="1990-05-15T10:00Z",
                correction_count=3,
            )
            session.add(p_bad)
            with pytest.raises(IntegrityError):
                await session.commit()
    finally:
        await engine.dispose()


def test_migration_revision_chain() -> None:
    module = _load_migration_module()
    assert module.revision == "0004_profiles_saju_charts"
    assert module.down_revision == "0003_users_devices"


def test_migration_declares_profiles_and_saju_charts() -> None:
    src = MIGRATION_PATH.read_text(encoding="utf-8")
    assert "create_table" in src
    assert '"profiles"' in src
    assert '"saju_charts"' in src


def test_saju_chart_model_has_expected_columns() -> None:
    cols = {c.name for c in inspect(SajuChart).columns}
    expected = {
        "id",
        "user_id",
        "chart_hash",
        "engine_version",
        "pillars",
        "time_known",
        "created_at",
    }
    missing = expected - cols
    assert not missing, f"SajuChart missing columns: {missing}"
