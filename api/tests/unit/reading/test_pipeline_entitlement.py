"""Unit test for ISSUE-039 entitlement gating.

AC: "Given an entitlement is missing, when ``POST /api/v1/reading`` is
called, then 402 with ``error.code='payment_required'``."

The endpoint calls
:func:`voicesaju.entitlement.service.check_entitlement` before creating
the Reading row. When the caller has no FreeToken and no active
subscription, the response is 402 + ``error.code='payment_required'``
and NO ``Reading`` row is persisted.
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
    Profile,
    Reading,
    User,
)
from voicesaju.jobs.worker import InMemoryQueue
from voicesaju.main import create_app
from voicesaju.storage.r2_client import R2Client


@pytest.fixture(autouse=True)
def _local_kek_env(monkeypatch: pytest.MonkeyPatch) -> None:
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


async def _seed_user_no_entitlement(engine: AsyncEngine) -> str:
    """Insert a user + profile but NO FreeToken/Subscription."""
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as s:
        u = User(kakao_sub="kakao-no-ent")
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


def test_post_reading_without_entitlement_returns_402(
    engine: AsyncEngine, tmp_path: Path
) -> None:
    """AC: missing entitlement → 402, error.code=payment_required, no row."""
    user_id = asyncio.run(_seed_user_no_entitlement(engine))
    client = _make_client(engine, user_id, tmp_path)

    resp = client.post("/api/v1/reading", json={"category": "love"})

    assert resp.status_code == 402, resp.text
    body = resp.json()
    # The FastAPI default error envelope wraps {detail: ...}. We accept
    # either ``body["error"]["code"]`` (custom envelope) or
    # ``body["detail"]["error"]["code"]`` (when wrapped) — but we prefer
    # the canonical custom envelope.
    error_block = body.get("error") or body.get("detail", {}).get("error", {})
    assert error_block.get("code") == "payment_required", body

    # No Reading row was created.
    maker = async_sessionmaker(engine, expire_on_commit=False)

    async def _count() -> int:
        async with maker() as s:
            return int(
                (
                    await s.execute(select(func.count()).select_from(Reading))
                ).scalar_one()
            )

    assert asyncio.run(_count()) == 0
