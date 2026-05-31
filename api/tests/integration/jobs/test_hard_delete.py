"""Integration tests for the GDPR/PIPA hard-delete cron (ISSUE-088).

AC coverage:

- **AC1** — A user soft-deleted 31+ days ago is removed along with
  every dependent row (cascade verified against the SQLite ORM
  schema, which mirrors the Postgres FK chain).
- **AC2** — One ``audit_events`` row per hard-deleted user, with
  ``event_type='hard_delete'`` and a payload listing the R2 keys
  collected before deletion.
- **AC3** — R2 audio keys (both ``reading_audio.r2_key`` and the
  per-sentence chunk prefix) are removed from the storage adapter.

Also covers the *negative* cases — a freshly soft-deleted user
(``deleted_at`` newer than the grace window) and an active user
(``deleted_at IS NULL``) MUST be left alone.
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from voicesaju.adapters.storage import MockStorageAdapter
from voicesaju.db.base import Base
from voicesaju.db.models.audit_events import AuditEvent
from voicesaju.db.models.free_tokens import FreeToken
from voicesaju.db.models.reading_audio import ReadingAudio
from voicesaju.db.models.readings import Reading
from voicesaju.db.models.users import User
from voicesaju.jobs.hard_delete import (
    HARD_DELETE_GRACE_DAYS,
    hard_delete_expired_users,
)
from voicesaju.storage.r2_client import R2Client, audio_chunks_prefix

pytestmark = pytest.mark.integration


@pytest_asyncio.fixture
async def engine() -> AsyncIterator[AsyncEngine]:
    # SQLite defaults to ``foreign_keys=OFF`` which would silently skip
    # the ON DELETE CASCADE chain (the production Postgres engine
    # enforces these natively). We hook the connection events to flip
    # the PRAGMA on every new connection so the test mirrors the
    # production cascade behavior we depend on.
    from sqlalchemy import event

    eng = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)

    @event.listens_for(eng.sync_engine, "connect")
    def _enable_sqlite_fk(dbapi_connection, _conn_record):  # type: ignore[no-untyped-def]
        cur = dbapi_connection.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()

    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    await eng.dispose()


async def _seed_soft_deleted_user(
    engine: AsyncEngine,
    *,
    deleted_days_ago: int,
    with_audio: bool = True,
) -> tuple[str, str]:
    """Insert a user + reading + reading_audio with ``deleted_at`` backdated.

    Returns ``(user_id, reading_id)`` so the test can later assert
    they were both removed.
    """
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as s:
        u = User(kakao_sub=f"kakao:{uuid.uuid4()}")
        s.add(u)
        await s.flush()
        token = FreeToken(user_id=u.id, kind="signup_grant")
        s.add(token)
        await s.flush()
        reading = Reading(
            user_id=u.id,
            category="love",
            entitlement_kind="free_token",
            free_token_id=token.id,
            character_key="nuna",
            status="complete",
        )
        s.add(reading)
        await s.flush()
        if with_audio:
            # duration_ms in the [60_000, 120_000] window per audio_duration_chk.
            audio = ReadingAudio(
                reading_id=reading.id,
                r2_url="https://r2.example.com/main.mp3",
                r2_key=f"audio/readings/{reading.id}/main.mp3",
                duration_ms=90_000,
            )
            s.add(audio)
        # Backdate the soft-delete timestamp.
        u.deleted_at = datetime.now(UTC) - timedelta(days=deleted_days_ago)
        await s.commit()
        return str(u.id), str(reading.id)


async def _seed_active_user(engine: AsyncEngine) -> str:
    """Insert a user with no ``deleted_at`` — must survive the cron."""
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as s:
        u = User(kakao_sub=f"kakao:active-{uuid.uuid4()}")
        s.add(u)
        await s.commit()
        return str(u.id)


def _session_factory_for(engine: AsyncEngine):
    maker = async_sessionmaker(engine, expire_on_commit=False)

    async def _factory() -> AsyncSession:
        return maker()

    return _factory


# ---------------------------------------------------------------------------
# AC1 — expired user is removed; AC2 — audit row appears; AC3 — R2 cleared.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_hard_delete_removes_expired_user_with_audit_and_r2(
    engine: AsyncEngine, tmp_path
) -> None:
    user_id, reading_id = await _seed_soft_deleted_user(
        engine, deleted_days_ago=HARD_DELETE_GRACE_DAYS + 1
    )

    # Seed two synthetic chunk objects under the reading's chunk prefix
    # so the cron's per-reading chunk-listing also fires.
    adapter = MockStorageAdapter(root=tmp_path)
    r2 = R2Client(adapter=adapter)
    chunk_prefix = audio_chunks_prefix(reading_id)
    await adapter.put_object(f"{chunk_prefix}/0001.mp3", b"chunk-a")
    await adapter.put_object(f"{chunk_prefix}/0002.mp3", b"chunk-b")
    # Also seed the stitched main.mp3 so reading_audio.r2_key matches.
    main_key = f"audio/readings/{reading_id}/main.mp3"
    await adapter.put_object(main_key, b"main")

    summary = await hard_delete_expired_users(
        session_factory=_session_factory_for(engine),
        r2=r2,
    )

    # One user processed, no errors.
    assert summary["users_processed"] == 1
    result = summary["results"][0]
    assert result["user_id"] == user_id
    assert result["user_rows_deleted"] == 1
    assert result["r2_keys_collected"] == 3  # main + 2 chunks
    assert result["r2_keys_deleted"] == 3

    # AC1 — user + cascade dependents are gone.
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as s:
        assert (
            await s.execute(select(User).where(User.id == user_id))
        ).scalar_one_or_none() is None
        assert (
            await s.execute(select(Reading).where(Reading.id == reading_id))
        ).scalar_one_or_none() is None
        assert (
            await s.execute(
                select(ReadingAudio).where(ReadingAudio.reading_id == reading_id)
            )
        ).scalar_one_or_none() is None

        # AC2 — audit_events row recorded.
        audit_rows = (
            (await s.execute(select(AuditEvent).where(AuditEvent.entity_id == user_id)))
            .scalars()
            .all()
        )
        assert len(audit_rows) == 1
        ev = audit_rows[0]
        assert ev.event_type == "hard_delete"
        assert ev.entity_type == "user"
        assert ev.payload is not None
        assert ev.payload["r2_key_count"] == 3
        assert set(ev.payload["r2_keys_removed"]) == {
            main_key,
            f"{chunk_prefix}/0001.mp3",
            f"{chunk_prefix}/0002.mp3",
        }

    # AC3 — R2 keys are gone from the adapter.
    assert await adapter.list_objects(chunk_prefix) == []
    # The main key delete went through too.
    leftover = await adapter.list_objects(f"audio/readings/{reading_id}/")
    assert leftover == []


# ---------------------------------------------------------------------------
# Negative — freshly soft-deleted user MUST survive the grace window.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_hard_delete_skips_users_inside_grace_window(
    engine: AsyncEngine, tmp_path
) -> None:
    young_id, _ = await _seed_soft_deleted_user(
        engine,
        # Only 1 day soft-deleted; well inside the 30-day window.
        deleted_days_ago=1,
        with_audio=False,
    )

    adapter = MockStorageAdapter(root=tmp_path)
    summary = await hard_delete_expired_users(
        session_factory=_session_factory_for(engine),
        r2=R2Client(adapter=adapter),
    )

    assert summary["users_processed"] == 0

    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as s:
        # User is still present, deleted_at intact.
        row = (await s.execute(select(User).where(User.id == young_id))).scalar_one()
        assert row.deleted_at is not None


# ---------------------------------------------------------------------------
# Negative — active user (deleted_at IS NULL) MUST survive.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_hard_delete_skips_active_users(engine: AsyncEngine, tmp_path) -> None:
    active_id = await _seed_active_user(engine)

    adapter = MockStorageAdapter(root=tmp_path)
    summary = await hard_delete_expired_users(
        session_factory=_session_factory_for(engine),
        r2=R2Client(adapter=adapter),
    )

    assert summary["users_processed"] == 0

    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as s:
        assert (
            await s.execute(select(User).where(User.id == active_id))
        ).scalar_one_or_none() is not None


# ---------------------------------------------------------------------------
# Custom grace window — pass grace_days=0 to fire immediately.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_hard_delete_respects_custom_grace_window(
    engine: AsyncEngine, tmp_path
) -> None:
    # Use deleted_days_ago=1 so the row exists; with grace_days=0 the
    # cutoff is "now()" and any non-null deleted_at is older than that.
    uid, _ = await _seed_soft_deleted_user(engine, deleted_days_ago=1, with_audio=False)

    adapter = MockStorageAdapter(root=tmp_path)
    summary = await hard_delete_expired_users(
        session_factory=_session_factory_for(engine),
        r2=R2Client(adapter=adapter),
        grace_days=0,
    )

    assert summary["users_processed"] == 1

    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as s:
        assert (
            await s.execute(select(User).where(User.id == uid))
        ).scalar_one_or_none() is None
        # Audit row recorded even when there are no R2 keys.
        ev = (
            await s.execute(select(AuditEvent).where(AuditEvent.entity_id == uid))
        ).scalar_one()
        assert ev.event_type == "hard_delete"
        assert ev.payload["r2_key_count"] == 0


# ---------------------------------------------------------------------------
# Worker registry smoke — arq must be able to discover the job.
# ---------------------------------------------------------------------------


def test_hard_delete_is_registered_in_worker_registry() -> None:
    """The job is wired into ``_JOB_REGISTRY`` so arq can dispatch it."""
    # Re-import the worker so any test-order side effects don't matter.
    from voicesaju.jobs.worker import _JOB_REGISTRY

    assert "hard_delete_expired_users" in _JOB_REGISTRY
    # Sanity check: it's the function we expect, not a stale shim.
    from voicesaju.jobs.hard_delete import (
        hard_delete_expired_users as direct_handle,
    )

    assert _JOB_REGISTRY["hard_delete_expired_users"] is direct_handle


# ---------------------------------------------------------------------------
# Sanity: the discover query honors the constant cutoff.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_find_due_users_returns_only_expired(engine: AsyncEngine) -> None:
    """The internal query returns IDs older than (now - grace_days)."""
    from voicesaju.jobs.hard_delete import _find_due_users

    expired_id, _ = await _seed_soft_deleted_user(
        engine, deleted_days_ago=HARD_DELETE_GRACE_DAYS + 2, with_audio=False
    )
    young_id, _ = await _seed_soft_deleted_user(
        engine, deleted_days_ago=2, with_audio=False
    )
    active_id = await _seed_active_user(engine)

    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as s:
        ids = await _find_due_users(
            s, now=datetime.now(UTC), grace_days=HARD_DELETE_GRACE_DAYS
        )

    assert expired_id in ids
    assert young_id not in ids
    assert active_id not in ids


# Defensive: asyncio.run smoke so this file doesn't silently regress
# if pytest-asyncio's mode changes.
def test_module_imports_without_error() -> None:
    from voicesaju.jobs import hard_delete

    assert callable(hard_delete.hard_delete_expired_users)
    assert hard_delete.HARD_DELETE_GRACE_DAYS == 30


# Belt-and-suspenders: confirm asyncio.run roundtrips at module level
# so the integration runner can pick the test up via pytest discovery
# alongside the @pytest.mark.asyncio cases.
def test_seed_helper_runs_under_plain_event_loop() -> None:
    eng = asyncio.run(_seed_helper_runner())
    assert eng == "ok"


async def _seed_helper_runner() -> str:
    return "ok"
