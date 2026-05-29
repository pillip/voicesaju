"""Unit tests for voicesaju.db.engine — async engine + sessionmaker."""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
)

from voicesaju.config import Settings
from voicesaju.db import engine as engine_mod


def test_build_async_url_rewrites_postgresql_scheme():
    raw = "postgresql://user:pw@host:5432/db"
    assert engine_mod.build_async_url(raw) == (
        "postgresql+asyncpg://user:pw@host:5432/db"
    )


def test_build_async_url_keeps_existing_asyncpg_scheme():
    raw = "postgresql+asyncpg://user:pw@host:5432/db"
    assert engine_mod.build_async_url(raw) == raw


def test_build_async_url_passes_through_other_schemes():
    raw = "sqlite+aiosqlite:///:memory:"
    assert engine_mod.build_async_url(raw) == raw


def test_create_engine_returns_async_engine():
    settings = Settings(
        database_url="sqlite+aiosqlite:///:memory:",
        db_pool_size=5,
        db_max_overflow=10,
    )
    eng = engine_mod.create_engine(settings)
    assert isinstance(eng, AsyncEngine)


@pytest.mark.asyncio
async def test_engine_creates_session(monkeypatch):
    """Session yields cleanly and round-trips a trivial SELECT.

    Uses in-memory SQLite via aiosqlite to avoid Postgres dependency.
    """
    # Install aiosqlite engine for the cached lookup
    settings = Settings(database_url="sqlite+aiosqlite:///:memory:")
    engine_mod.reset_engine_cache()
    monkeypatch.setattr(engine_mod, "get_settings", lambda: settings)

    sessionmaker = engine_mod.get_sessionmaker()
    assert isinstance(sessionmaker, async_sessionmaker)

    async with sessionmaker() as session:
        assert isinstance(session, AsyncSession)
        from sqlalchemy import text

        result = await session.execute(text("SELECT 1"))
        assert result.scalar() == 1

    engine_mod.reset_engine_cache()


@pytest.mark.asyncio
async def test_get_session_dependency_yields_session(monkeypatch):
    """`get_session` is an async generator dependency for FastAPI."""
    settings = Settings(database_url="sqlite+aiosqlite:///:memory:")
    engine_mod.reset_engine_cache()
    monkeypatch.setattr(engine_mod, "get_settings", lambda: settings)

    gen = engine_mod.get_session()
    session = await gen.__anext__()
    try:
        assert isinstance(session, AsyncSession)
    finally:
        with pytest.raises(StopAsyncIteration):
            await gen.__anext__()

    engine_mod.reset_engine_cache()
