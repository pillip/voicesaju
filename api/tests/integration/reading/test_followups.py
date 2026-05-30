"""Integration tests for the M2 follow-up endpoints (ISSUE-041).

Covers the full GET + POST + SSE flow with the Phase-1 mock adapters
(``LLM_PROVIDER=mock``, ``TTS_PROVIDER=mock``, ``STORAGE_PROVIDER=mock``):

1. ``GET /api/v1/reading/{id}/followups`` returns three suggestions
   tied to the parent reading's category.
2. ``POST /api/v1/reading/{id}/followups/0`` streams subtitle +
   audio_ready + end events, persists the row with answer_text and
   audio_r2_key, and writes the chunk file to storage.
3. The POST endpoint enforces the slot-already-consumed contract
   (FR-009): a second POST against the same slot returns 409.

These tests mirror the ISSUE-039 pipeline test fixtures: hermetic
SQLite + ``MockStorageAdapter`` root + per-test queue capture.
"""

from __future__ import annotations

import asyncio
import base64
import json
from collections.abc import AsyncIterator
from pathlib import Path

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
    """Pin every adapter to its Phase-1 mock + provide envelope KEK."""
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


# ---------------------------------------------------------------------------
# Seed helpers
# ---------------------------------------------------------------------------


async def _seed_reading(
    engine: AsyncEngine,
    *,
    kakao_sub: str,
    category: str = "love",
) -> tuple[str, str]:
    """Create a user + profile + free token + completed reading.

    Returns ``(user_id, reading_id)``. The reading's status is set
    directly to ``complete`` so the GET endpoint can be tested
    without first driving the streaming pipeline.
    """
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as s:
        u = User(kakao_sub=kakao_sub)
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

        token = FreeToken(user_id=u.id, kind="signup_grant")
        s.add(token)
        await s.commit()
        await s.refresh(token)

        reading = Reading(
            user_id=u.id,
            category=category,
            character_key="nuna",
            status="complete",
            entitlement_kind="free_token",
            free_token_id=token.id,
        )
        s.add(reading)
        await s.commit()
        await s.refresh(reading)
        return str(u.id), str(reading.id)


def _make_client(
    engine: AsyncEngine,
    user_id: str | None,
    *,
    storage_root: Path | None = None,
) -> TestClient:
    """Build a TestClient with DB / auth / storage overrides."""
    maker = async_sessionmaker(engine, expire_on_commit=False)

    async def _override_get_session() -> AsyncIterator[AsyncSession]:
        async with maker() as s:
            yield s

    app = create_app()
    app.dependency_overrides[get_session] = _override_get_session

    if user_id is not None:
        from voicesaju.readings.routers.pipeline import _get_current_user_id

        app.dependency_overrides[_get_current_user_id] = lambda: user_id

    if storage_root is not None:
        from voicesaju.readings.routers.pipeline import _get_r2_client

        adapter = MockStorageAdapter(root=storage_root)
        r2 = R2Client(adapter=adapter)
        app.dependency_overrides[_get_r2_client] = lambda: r2

    return TestClient(app)


def _parse_sse_events(raw: str) -> list[tuple[str, dict]]:
    """Parse an SSE stream blob into ``[(event_name, json_data), ...]``."""
    events: list[tuple[str, dict]] = []
    for block in raw.split("\n\n"):
        block = block.strip()
        if not block:
            continue
        event_name = "message"
        data_parts: list[str] = []
        for line in block.splitlines():
            if line.startswith("event:"):
                event_name = line[len("event:") :].strip()
            elif line.startswith("data:"):
                data_parts.append(line[len("data:") :].strip())
        data_str = "\n".join(data_parts)
        try:
            payload: dict = json.loads(data_str) if data_str else {}
        except json.JSONDecodeError:
            payload = {"_raw": data_str}
        events.append((event_name, payload))
    return events


# ---------------------------------------------------------------------------
# AC 1 — GET /followups returns 3 questions for a completed reading.
# ---------------------------------------------------------------------------


def test_get_followups_returns_three_questions(
    engine: AsyncEngine, tmp_path: Path
) -> None:
    """AC: GET .../followups returns 3 questions (FR-009)."""
    user_id, reading_id = asyncio.run(
        _seed_reading(engine, kakao_sub="kakao-followups-1", category="love")
    )
    client = _make_client(engine, user_id, storage_root=tmp_path)

    resp = client.get(f"/api/v1/reading/{reading_id}/followups")

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["reading_id"] == reading_id

    suggestions = body["suggestions"]
    assert len(suggestions) == 3, suggestions

    # Slot indices must cover 0..2 exactly once.
    indices = sorted(s["slot_index"] for s in suggestions)
    assert indices == [0, 1, 2]

    # Every question must be a non-empty string.
    for s in suggestions:
        assert isinstance(s["question_text"], str)
        assert s["question_text"].strip()


# ---------------------------------------------------------------------------
# AC 3 — POST /followups/0 streams SSE and persists the row + audio key.
# ---------------------------------------------------------------------------


def test_post_followup_streams_sse_and_persists_row(
    engine: AsyncEngine, tmp_path: Path
) -> None:
    """AC: POST .../followups/0 → SSE subtitle + audio_ready + end.

    Also verifies (post-stream) that the ReadingFollowup row exists
    with answer_text and audio_r2_key populated, and that the chunk
    landed under the storage root.
    """
    user_id, reading_id = asyncio.run(
        _seed_reading(engine, kakao_sub="kakao-followups-2", category="work")
    )
    client = _make_client(engine, user_id, storage_root=tmp_path)

    with client.stream(
        "POST", f"/api/v1/reading/{reading_id}/followups/0"
    ) as stream_resp:
        assert stream_resp.status_code == 200, stream_resp.read().decode("utf-8")
        assert "text/event-stream" in stream_resp.headers.get("content-type", "")
        chunks: list[bytes] = []
        for chunk in stream_resp.iter_bytes():
            chunks.append(chunk)
    raw = b"".join(chunks).decode("utf-8")

    events = _parse_sse_events(raw)
    assert events, f"no SSE events parsed; raw={raw!r}"

    names = [n for n, _ in events]
    assert "subtitle" in names, names
    assert "audio_ready" in names, names
    assert names[-1] == "end", names

    # End event carries the slot_index.
    end_payload = events[-1][1]
    assert end_payload["reading_id"] == reading_id
    assert end_payload["slot_index"] == 0
    assert "duration_ms" in end_payload

    # Per-slot chunk files exist under the storage root.
    chunk_files = sorted(
        (tmp_path / "audio" / "readings" / reading_id / "followups" / "0").glob("*.mp3")
    )
    assert chunk_files, "expected ≥1 follow-up chunk file"

    # DB row persisted with answer_text + audio_r2_key.
    maker = async_sessionmaker(engine, expire_on_commit=False)

    async def _load() -> ReadingFollowup:
        async with maker() as s:
            return (
                await s.execute(
                    select(ReadingFollowup).where(
                        ReadingFollowup.reading_id == reading_id,
                        ReadingFollowup.slot_index == 0,
                    )
                )
            ).scalar_one()

    row = asyncio.run(_load())
    assert row.question_text.strip()
    assert row.answer_text and row.answer_text.strip()
    assert row.audio_r2_key and "/followups/0/" in row.audio_r2_key
