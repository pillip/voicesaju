"""Integration tests for the M2 reading pipeline (ISSUE-039).

Covers the full POST + SSE flow with the Phase-1 mock adapters
(``LLM_PROVIDER=mock``, ``TTS_PROVIDER=mock``, ``STORAGE_PROVIDER=mock``):

1. ``POST /api/v1/reading`` with a valid entitlement creates a
   ``Reading`` row, returns 201 ``{reading_id, sse_url, audio_stream_url}``.
2. ``GET /api/v1/reading/{id}/stream`` orchestrates the chart_lookup →
   LLM → guardrail → TTS → R2 chunk upload → SSE emit pipeline and emits
   ``subtitle`` + ``audio_ready`` events in order, terminating on ``end``.
3. After the SSE stream completes, audio chunks exist under
   ``audio/readings/{reading_id}/chunks/`` and a ``finalize_audio`` job
   has been enqueued.

These tests use ``MockStorageAdapter(root=tmp_path)`` so each test gets
its own filesystem root and the chunks don't leak into ``./.local_storage/``.
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
    User,
)
from voicesaju.jobs.worker import InMemoryQueue
from voicesaju.main import create_app
from voicesaju.storage.r2_client import R2Client


@pytest.fixture(autouse=True)
def _local_kek_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Provide deterministic env for envelope encryption + provider mocks."""
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


async def _seed_user_with_free_token(
    engine: AsyncEngine,
    *,
    kakao_sub: str = "kakao-pipeline-1",
) -> tuple[str, str]:
    """Insert a user + profile + unconsumed signup_grant FreeToken.

    Returns ``(user_id, token_id)``.
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
        return str(u.id), str(token.id)


async def _seed_user_no_entitlement(
    engine: AsyncEngine,
    *,
    kakao_sub: str = "kakao-no-ent",
) -> str:
    """Insert a user + profile but NO FreeToken/Subscription."""
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
        await s.commit()
        return str(u.id)


def _make_client(
    engine: AsyncEngine,
    user_id: str | None,
    *,
    storage_root: Path | None = None,
    queue: InMemoryQueue | None = None,
) -> TestClient:
    """Build a TestClient with DB / auth / storage / queue overrides."""
    maker = async_sessionmaker(engine, expire_on_commit=False)

    async def _override_get_session() -> AsyncIterator[AsyncSession]:
        async with maker() as s:
            yield s

    app = create_app()
    app.dependency_overrides[get_session] = _override_get_session

    # Auth override
    if user_id is not None:
        from voicesaju.readings.routers.pipeline import (
            _get_current_user_id,
        )

        app.dependency_overrides[_get_current_user_id] = lambda: user_id

    # Storage override — bind a hermetic local-fs root.
    if storage_root is not None:
        from voicesaju.readings.routers.pipeline import _get_r2_client

        adapter = MockStorageAdapter(root=storage_root)
        r2 = R2Client(adapter=adapter)
        app.dependency_overrides[_get_r2_client] = lambda: r2

    # Queue override — capture enqueued jobs for the post-stream assertion.
    if queue is not None:
        from voicesaju.readings.routers.pipeline import _get_finalize_queue

        app.dependency_overrides[_get_finalize_queue] = lambda: queue

    return TestClient(app)


def _parse_sse_events(raw: str) -> list[tuple[str, dict]]:
    """Parse an SSE stream blob into a list of ``(event_name, json_data)``."""
    events: list[tuple[str, dict]] = []
    current_event: str | None = None
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
        if not data_str:
            payload: dict = {}
        else:
            try:
                payload = json.loads(data_str)
            except json.JSONDecodeError:
                payload = {"_raw": data_str}
        events.append((event_name, payload))
        _ = current_event  # quiet pyright re unused
    return events


# ---------------------------------------------------------------------------
# AC 1 — POST creates Reading row and returns 201 with the contract.
# ---------------------------------------------------------------------------


def test_post_reading_creates_row_and_returns_urls(
    engine: AsyncEngine, tmp_path: Path
) -> None:
    """AC: ``POST /api/v1/reading`` with valid entitlement → 201 envelope."""
    user_id, _token_id = asyncio.run(_seed_user_with_free_token(engine))
    queue = InMemoryQueue()
    client = _make_client(engine, user_id, storage_root=tmp_path, queue=queue)

    resp = client.post(
        "/api/v1/reading",
        json={"category": "love"},
    )

    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert "reading_id" in body
    assert body["sse_url"].endswith(f"/api/v1/reading/{body['reading_id']}/stream")
    assert body["audio_stream_url"].endswith(
        f"/api/v1/reading/{body['reading_id']}/audio"
    )

    # Reading row must exist with the requested category + correct
    # entitlement_kind. character_key is hardcoded to "nuna" for M2.
    maker = async_sessionmaker(engine, expire_on_commit=False)

    async def _verify() -> Reading:
        async with maker() as s:
            row = (
                await s.execute(select(Reading).where(Reading.id == body["reading_id"]))
            ).scalar_one()
            return row

    row = asyncio.run(_verify())
    assert row.category == "love"
    assert row.status in ("pending", "streaming")
    assert row.character_key == "nuna"
    assert row.entitlement_kind == "free_token"
    assert row.free_token_id is not None


# ---------------------------------------------------------------------------
# AC 3 — SSE stream emits subtitle + audio_ready + end (in order).
# ---------------------------------------------------------------------------


def test_sse_stream_emits_subtitle_audio_ready_and_end(
    engine: AsyncEngine, tmp_path: Path
) -> None:
    """AC: SSE stream connects → ``subtitle`` + ``audio_ready`` → ``end``.

    Also verifies (post-stream) that chunk files exist under the storage
    prefix and a ``finalize_audio`` job has been enqueued.
    """
    user_id, _token_id = asyncio.run(_seed_user_with_free_token(engine))
    queue = InMemoryQueue()
    client = _make_client(engine, user_id, storage_root=tmp_path, queue=queue)

    # Create the reading first.
    post_resp = client.post("/api/v1/reading", json={"category": "love"})
    assert post_resp.status_code == 201, post_resp.text
    reading_id = post_resp.json()["reading_id"]

    # Consume the SSE stream.
    with client.stream("GET", f"/api/v1/reading/{reading_id}/stream") as stream_resp:
        assert stream_resp.status_code == 200, stream_resp.read().decode("utf-8")
        assert "text/event-stream" in stream_resp.headers.get("content-type", "")
        chunks: list[bytes] = []
        for chunk in stream_resp.iter_bytes():
            chunks.append(chunk)
    raw = b"".join(chunks).decode("utf-8")

    events = _parse_sse_events(raw)
    assert events, f"no SSE events parsed; raw={raw!r}"

    event_names = [name for name, _ in events]
    assert "subtitle" in event_names, event_names
    assert "audio_ready" in event_names, event_names
    assert event_names[-1] == "end", event_names

    # subtitle MUST come before audio_ready in the stream order — the
    # frontend's NFR-015 subtitle scheduler depends on this ordering.
    first_subtitle = event_names.index("subtitle")
    first_audio = event_names.index("audio_ready")
    assert (
        first_subtitle < first_audio
    ), f"subtitle must precede audio_ready: {event_names}"

    # Each audio_ready event carries a chunk URL.
    audio_events = [data for name, data in events if name == "audio_ready"]
    assert audio_events, "expected ≥1 audio_ready event"
    for data in audio_events:
        assert "url" in data, data
        assert "seq" in data, data

    # Each subtitle carries text + audio_offset_ms.
    subtitle_events = [data for name, data in events if name == "subtitle"]
    for data in subtitle_events:
        assert "text" in data and isinstance(data["text"], str)
        assert "audio_offset_ms" in data and isinstance(data["audio_offset_ms"], int)

    # Chunks must exist on disk under the storage root.
    chunk_files = sorted(
        (tmp_path / "audio" / "readings" / reading_id / "chunks").glob("*.mp3")
    )
    assert (
        len(chunk_files) >= 1
    ), f"expected ≥1 chunk file under storage root, found {chunk_files}"

    # ``finalize_audio`` should be enqueued.
    assert len(queue) == 1, f"expected 1 enqueued finalize_audio, got {len(queue)}"
