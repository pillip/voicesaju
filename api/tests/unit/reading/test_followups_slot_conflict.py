"""Unit test for the follow-up slot conflict contract (ISSUE-041).

A second POST against an already-consumed slot must return 409 with
the structured ``slot_already_consumed`` error envelope and MUST NOT
create a second ``ReadingFollowup`` row.

This is the server-side button-disable contract from the issue spec
(FR-009 AC): the frontend's optimistic disable is backed by 409s so
quick double-taps or race conditions still produce one Q+A per slot.
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
    ReadingFollowup,
    User,
)
from voicesaju.main import create_app
from voicesaju.storage.r2_client import R2Client


@pytest.fixture(autouse=True)
def _env_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_kek = base64.b64encode(b"\x00" * 32).decode("ascii")
    monkeypatch.setenv("LOCAL_KEK_BASE64", fake_kek)
    monkeypatch.setenv("KMS_PROVIDER", "local")
    monkeypatch.setenv("LLM_PROVIDER", "mock")
    monkeypatch.setenv("TTS_PROVIDER", "mock")
    monkeypatch.setenv("STORAGE_PROVIDER", "mock")


@pytest_asyncio.fixture
async def engine() -> AsyncIterator[AsyncEngine]:
    eng = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    await eng.dispose()


async def _seed(engine: AsyncEngine) -> tuple[str, str]:
    """Create user + profile + free token + completed reading.

    Returns ``(user_id, reading_id)``.
    """
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as s:
        u = User(kakao_sub="kakao-slot-conflict")
        s.add(u)
        await s.commit()
        await s.refresh(u)

        p = Profile(user_id=u.id, birth_time_known=True, birth_is_lunar=False)
        p.birth_dt = "1997-08-13T07:30"
        s.add(p)
        token = FreeToken(user_id=u.id, kind="signup_grant")
        s.add(token)
        await s.commit()
        await s.refresh(token)

        reading = Reading(
            user_id=u.id,
            category="love",
            character_key="nuna",
            status="complete",
            entitlement_kind="free_token",
            free_token_id=token.id,
        )
        s.add(reading)
        await s.commit()
        await s.refresh(reading)
        return str(u.id), str(reading.id)


def _make_client(engine: AsyncEngine, user_id: str, storage_root: Path) -> TestClient:
    maker = async_sessionmaker(engine, expire_on_commit=False)

    async def _override_session() -> AsyncIterator[AsyncSession]:
        async with maker() as s:
            yield s

    app = create_app()
    app.dependency_overrides[get_session] = _override_session

    from voicesaju.readings.routers.pipeline import (
        _get_current_user_id,
        _get_r2_client,
    )

    app.dependency_overrides[_get_current_user_id] = lambda: user_id
    adapter = MockStorageAdapter(root=storage_root)
    r2 = R2Client(adapter=adapter)
    app.dependency_overrides[_get_r2_client] = lambda: r2

    return TestClient(app)


def test_second_post_to_same_slot_returns_409(
    engine: AsyncEngine, tmp_path: Path
) -> None:
    """AC: POST .../followups/0 twice → second returns 409 conflict.

    The first POST must drain its SSE stream so the row commits before
    the second POST races the unique check.
    """
    user_id, reading_id = asyncio.run(_seed(engine))
    client = _make_client(engine, user_id, tmp_path)

    # First call — drain the SSE stream completely so the row commits.
    with client.stream("POST", f"/api/v1/reading/{reading_id}/followups/0") as first:
        assert first.status_code == 200, first.read().decode("utf-8")
        for _ in first.iter_bytes():
            pass

    # Second call to the same slot → 409.
    second = client.post(f"/api/v1/reading/{reading_id}/followups/0")
    assert second.status_code == 409, second.text
    body = second.json()
    # FastAPI wraps the structured detail under "detail".
    error = body.get("detail", {}).get("error") or body.get("error")
    assert error is not None, body
    assert error["code"] == "slot_already_consumed"

    # Only one row exists for this (reading_id, slot_index).
    maker = async_sessionmaker(engine, expire_on_commit=False)

    async def _count() -> int:
        async with maker() as s:
            stmt = (
                select(func.count())
                .select_from(ReadingFollowup)
                .where(
                    ReadingFollowup.reading_id == reading_id,
                    ReadingFollowup.slot_index == 0,
                )
            )
            return (await s.execute(stmt)).scalar_one()

    assert asyncio.run(_count()) == 1
