"""SQLAlchemy 2.0 async engine, sessionmaker, and FastAPI dependency.

The engine is created lazily on first request so that test suites can
override the URL via dependency injection without paying the connection
cost at import time.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from functools import lru_cache

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from voicesaju.config import Settings, get_settings


def build_async_url(url: str) -> str:
    """Normalise a database URL so SQLAlchemy uses the asyncpg driver.

    Accepts both `postgresql://` and `postgresql+asyncpg://` forms; returns
    the asyncpg-prefixed form. Non-Postgres URLs (e.g. `sqlite+aiosqlite://`)
    are returned untouched so test suites can swap in lightweight backends.
    """
    if url.startswith("postgresql+asyncpg://"):
        return url
    if url.startswith("postgresql://"):
        return "postgresql+asyncpg://" + url[len("postgresql://") :]
    return url


def create_engine(settings: Settings | None = None) -> AsyncEngine:
    """Build a new async engine from settings.

    Intentionally not cached — callers that want a process-wide singleton
    should use `get_engine()`. Pool-tuning kwargs are only forwarded for
    Postgres so test suites can use SQLite (which uses StaticPool).
    """
    settings = settings or get_settings()
    url = build_async_url(settings.database_url)
    kwargs: dict[str, object] = {"echo": settings.db_echo}
    if url.startswith("postgresql"):
        kwargs.update(
            pool_size=settings.db_pool_size,
            max_overflow=settings.db_max_overflow,
            pool_pre_ping=True,
        )
    return create_async_engine(url, **kwargs)


@lru_cache(maxsize=1)
def get_engine() -> AsyncEngine:
    """Return the process-wide async engine, creating it on first call."""
    return create_engine()


@lru_cache(maxsize=1)
def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    """Return the process-wide async sessionmaker bound to the cached engine."""
    return async_sessionmaker(
        bind=get_engine(),
        expire_on_commit=False,
        class_=AsyncSession,
    )


async def get_session() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency that yields an `AsyncSession`.

    Use via `Depends(get_session)`. The session is closed automatically
    when the request finishes.
    """
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        yield session


def reset_engine_cache() -> None:
    """Clear the cached engine/sessionmaker (used by tests)."""
    get_engine.cache_clear()
    get_sessionmaker.cache_clear()
