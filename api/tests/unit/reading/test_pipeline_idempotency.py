"""Unit tests for ISSUE-039 idempotency.

AC: "Given the same Idempotency-Key is sent twice, when both arrive, then
only one Reading row exists." The POST endpoint reads ``Idempotency-Key``
from the request headers, persists it on the ``Reading`` row, and returns
the existing ``reading_id`` if the same key+user pair is replayed.

Tests use an in-memory SQLite engine + the same dependency-override
pattern as :mod:`tests.integration.reading.test_pipeline`. They focus
on the persistence side-effect (one row, same id) rather than the full
SSE pipeline.
"""

from __future__ import annotations

import asyncio
import base64
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from voicesaju.adapters.storage import MockStorageAdapter
from voicesaju.db.base import Base
from voicesaju.db.engine import get_session
from voicesaju.db.models import (  # noqa: F401 - register metadata
    FreeToken,
    Profile,
    Reading,
    User,
)
from voicesaju.jobs.worker import InMemoryQueue
from voicesaju.main import create_app
from voicesaju.storage.r2_client import R2Client


@pytest.fixture(autouse=True)
def _local_kek_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Provide deterministic env for envelope + mock providers."""
    fake_kek = base64.b64encode(b"\x00" * 32).decode("ascii")
    monkeypatch.setenv("LOCAL_KEK_BASE64", fake_kek)
    monkeypatch.setenv("KMS_PROVIDER", "local")
    monkeypatch.setenv("LLM_PROVIDER", "mock")
    monkeypatch.setenv("TTS_PROVIDER", "mock")
    monkeypatch.setenv("STORAGE_PROVIDER", "mock")


@pytest_asyncio.fixture
async def engine() -> AsyncIterator[AsyncEngine]:
    """Per-test SQLite engine with the full ORM schema reflected."""
    eng = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    await eng.dispose()


async def _seed_user_with_two_tokens(engine: AsyncEngine) -> str:
    """Insert a user + profile + two FreeTokens (so a 2nd reading would
    succeed unless idempotency short-circuits).
    """
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as s:
        u = User(kakao_sub="kakao-idem-1")
        s.add(u)
        await s.commit()
        await s.refresh(u)

        p = Profile(
            user_id=u.id,
            birth_time_known=True,
            birth_is_lunar=False,
        )
        p.birth_dt = "1997-08-13T07:30"
        s.add(p)

        # Two tokens — the test verifies idempotency, NOT entitlement
        # consumption. A future hardening pass may make tokens single-use
        # post-stream; today's test merely needs entitlement available.
        s.add(FreeToken(user_id=u.id, kind="signup_grant"))
        s.add(FreeToken(user_id=u.id, kind="ops_grant"))

        await s.commit()
        return str(u.id)


def _make_client(engine: AsyncEngine, user_id: str, storage_root: Path) -> TestClient:
    maker = async_sessionmaker(engine, expire_on_commit=False)

    async def _override_get_session() -> AsyncIterator[AsyncSession]:
        async with maker() as s:
            yield s

    app = create_app()
    app.dependency_overrides[get_session] = _override_get_session

    from voicesaju.readings.routers.pipeline import (
        _get_current_user_id,
        _get_finalize_queue,
        _get_r2_client,
    )

    app.dependency_overrides[_get_current_user_id] = lambda: user_id

    r2 = R2Client(adapter=MockStorageAdapter(root=storage_root))
    app.dependency_overrides[_get_r2_client] = lambda: r2
    app.dependency_overrides[_get_finalize_queue] = lambda: InMemoryQueue()

    return TestClient(app)


def test_idempotency_key_replay_returns_same_reading_id(
    engine: AsyncEngine, tmp_path: Path
) -> None:
    """AC: same ``Idempotency-Key`` twice → one Reading row, same id."""
    user_id = asyncio.run(_seed_user_with_two_tokens(engine))
    client = _make_client(engine, user_id, tmp_path)

    headers = {"Idempotency-Key": "same-key-abc-123"}
    resp1 = client.post("/api/v1/reading", json={"category": "love"}, headers=headers)
    assert resp1.status_code == 201, resp1.text
    first_id = resp1.json()["reading_id"]

    resp2 = client.post("/api/v1/reading", json={"category": "love"}, headers=headers)
    # The replay returns 200 (existing resource) or 201 with the same id;
    # the spec only mandates "only one row exists" + "second returns the
    # existing id". We accept either status — focus on the contract.
    assert resp2.status_code in (200, 201), resp2.text
    second_id = resp2.json()["reading_id"]
    assert first_id == second_id

    # Exactly one Reading row in the DB.
    maker = async_sessionmaker(engine, expire_on_commit=False)

    async def _count() -> int:
        async with maker() as s:
            return int(
                (
                    await s.execute(select(func.count()).select_from(Reading))
                ).scalar_one()
            )

    assert asyncio.run(_count()) == 1


def test_different_idempotency_keys_create_distinct_rows(
    engine: AsyncEngine, tmp_path: Path
) -> None:
    """Different ``Idempotency-Key`` values → distinct Reading rows.

    Sanity check that idempotency is scoped to the key — without it the
    short-circuit would deduplicate every request.
    """
    user_id = asyncio.run(_seed_user_with_two_tokens(engine))
    client = _make_client(engine, user_id, tmp_path)

    resp1 = client.post(
        "/api/v1/reading",
        json={"category": "love"},
        headers={"Idempotency-Key": "key-a"},
    )
    assert resp1.status_code == 201, resp1.text

    resp2 = client.post(
        "/api/v1/reading",
        json={"category": "love"},
        headers={"Idempotency-Key": "key-b"},
    )
    assert resp2.status_code == 201, resp2.text

    assert resp1.json()["reading_id"] != resp2.json()["reading_id"]
