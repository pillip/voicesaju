"""Tests for the audio finalize job (ISSUE-038)."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    async_sessionmaker,
    create_async_engine,
)

from voicesaju.adapters.storage import MockStorageAdapter
from voicesaju.db.base import Base
from voicesaju.db.models.free_tokens import FreeToken
from voicesaju.db.models.readings import Reading
from voicesaju.db.models.users import User
from voicesaju.jobs.audio_finalize import finalize_audio
from voicesaju.storage.r2_client import R2Client


@pytest_asyncio.fixture
async def engine() -> AsyncIterator[AsyncEngine]:
    eng = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    await eng.dispose()


async def _seed_reading(engine: AsyncEngine) -> str:
    """Create user + free_token + reading; return reading_id."""
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as s:
        u = User(kakao_sub="finalize-seed")
        s.add(u)
        await s.flush()
        token = FreeToken(user_id=u.id, kind="signup_grant")
        s.add(token)
        await s.flush()
        r = Reading(
            user_id=u.id,
            category="love",
            entitlement_kind="free_token",
            free_token_id=token.id,
            character_key="nuna",
            status="completed",
        )
        s.add(r)
        await s.commit()
        await s.refresh(r)
        return str(r.id)


@pytest.mark.asyncio
async def test_finalize_stitches_and_persists(tmp_path):
    eng = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    reading_id = await _seed_reading(eng)
    adapter = MockStorageAdapter(root=tmp_path)
    r2 = R2Client(adapter=adapter)

    # Upload three sentence chunks.
    await r2.put_chunk(reading_id, 0, b"\xff\xfb\x90\x00aaa")
    await r2.put_chunk(reading_id, 1, b"\xff\xfb\x90\x00bbb")
    await r2.put_chunk(reading_id, 2, b"\xff\xfb\x90\x00ccc")

    maker = async_sessionmaker(eng, expire_on_commit=False)
    async with maker() as s:
        result = await finalize_audio(reading_id, session=s, r2=r2)
        await s.commit()

    # AC1: stitched main exists with concatenated bytes.
    assert result.file_size_bytes == 3 * 7
    stitched = await adapter.get_object(f"audio/readings/{reading_id}/main.mp3")
    assert stitched == b"\xff\xfb\x90\x00aaa\xff\xfb\x90\x00bbb\xff\xfb\x90\x00ccc"

    # AC1: chunks were deleted.
    remaining = await adapter.list_objects(f"audio/readings/{reading_id}/chunks")
    assert remaining == []
    assert result.chunks_deleted == 3

    # AC2: reading_audio row has all the metadata.
    assert result.r2_key.endswith("/main.mp3")
    assert result.content_hash and len(result.content_hash) == 64
    assert result.file_size_bytes > 0
    assert result.duration_ms > 0


@pytest.mark.asyncio
async def test_finalize_raises_when_no_chunks(tmp_path):
    eng = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    reading_id = str(uuid.uuid4())
    adapter = MockStorageAdapter(root=tmp_path)
    r2 = R2Client(adapter=adapter)
    maker = async_sessionmaker(eng, expire_on_commit=False)
    async with maker() as s:
        with pytest.raises(ValueError, match="no chunks"):
            await finalize_audio(reading_id, session=s, r2=r2)


@pytest.mark.asyncio
async def test_finalize_is_idempotent_on_rerun(tmp_path):
    """Re-running finalize for the same reading_id updates the existing row."""
    eng = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    reading_id = await _seed_reading(eng)
    adapter = MockStorageAdapter(root=tmp_path)
    r2 = R2Client(adapter=adapter)
    await r2.put_chunk(reading_id, 0, b"\xff\xfb\x90\x00v1")
    maker = async_sessionmaker(eng, expire_on_commit=False)
    async with maker() as s:
        await finalize_audio(reading_id, session=s, r2=r2)
        await s.commit()

    # Second pass with a different chunk; main should overwrite.
    await r2.put_chunk(reading_id, 0, b"\xff\xfb\x90\x00v2-longer")
    async with maker() as s:
        result2 = await finalize_audio(reading_id, session=s, r2=r2)
        await s.commit()

    assert result2.file_size_bytes == len(b"\xff\xfb\x90\x00v2-longer")

    # Exactly one reading_audio row exists.
    async with maker() as s:
        from voicesaju.db.models.reading_audio import ReadingAudio

        rows = (await s.execute(select(ReadingAudio))).scalars().all()
        assert len(rows) == 1
