"""Integration tests for the soft-delete + logout endpoints (ISSUE-072)."""

from __future__ import annotations

import asyncio
import base64
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from voicesaju.db.base import Base
from voicesaju.db.engine import get_session
from voicesaju.db.models.profiles import Profile
from voicesaju.db.models.users import User
from voicesaju.main import create_app


@pytest.fixture(autouse=True)
def _env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LOCAL_KEK_BASE64", base64.b64encode(b"\x00" * 32).decode())
    monkeypatch.setenv("KMS_PROVIDER", "local")


@pytest_asyncio.fixture
async def engine() -> AsyncIterator[AsyncEngine]:
    eng = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    await eng.dispose()


async def _seed_user(engine: AsyncEngine, with_profile: bool = True) -> str:
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as s:
        u = User(kakao_sub="del-1")
        s.add(u)
        await s.flush()
        if with_profile:
            p = Profile(
                user_id=u.id,
                birth_dt_enc={"ciphertext": "x", "nonce": "y", "dek_version": 1},
                birth_is_lunar=False,
                birth_time_known=False,
            )
            s.add(p)
        await s.commit()
        await s.refresh(u)
        return str(u.id)


def _client(engine: AsyncEngine, user_id: str) -> TestClient:
    maker = async_sessionmaker(engine, expire_on_commit=False)

    async def _override() -> AsyncIterator[AsyncSession]:
        async with maker() as s:
            yield s

    app = create_app()
    app.dependency_overrides[get_session] = _override

    from voicesaju.users.routers.account import _get_current_user_id

    app.dependency_overrides[_get_current_user_id] = lambda: user_id
    return TestClient(app)


def test_delete_account_stamps_deleted_at_on_user_and_profile(
    engine: AsyncEngine,
) -> None:
    user_id = asyncio.run(_seed_user(engine, with_profile=True))
    client = _client(engine, user_id)

    resp = client.post("/api/v1/users/me/delete")
    assert resp.status_code == 200, resp.text
    assert resp.json() == {"ok": True}

    maker = async_sessionmaker(engine, expire_on_commit=False)

    async def _read() -> tuple[User, Profile | None]:
        async with maker() as s:
            u = (await s.execute(select(User).where(User.id == user_id))).scalar_one()
            p = (
                await s.execute(select(Profile).where(Profile.user_id == user_id))
            ).scalar_one_or_none()
            return u, p

    u, p = asyncio.run(_read())
    assert u.deleted_at is not None
    assert p is not None
    assert p.deleted_at is not None


def test_delete_account_is_idempotent(engine: AsyncEngine) -> None:
    user_id = asyncio.run(_seed_user(engine, with_profile=False))
    client = _client(engine, user_id)

    r1 = client.post("/api/v1/users/me/delete")
    r2 = client.post("/api/v1/users/me/delete")
    assert r1.status_code == 200
    assert r2.status_code == 200


def test_delete_account_clears_session_cookie(engine: AsyncEngine) -> None:
    user_id = asyncio.run(_seed_user(engine, with_profile=False))
    client = _client(engine, user_id)

    resp = client.post("/api/v1/users/me/delete")
    set_cookie = resp.headers.get("set-cookie", "")
    # Starlette emits a vs_sess delete header with an expired Max-Age.
    assert "vs_sess=" in set_cookie
