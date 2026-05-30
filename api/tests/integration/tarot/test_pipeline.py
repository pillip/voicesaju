"""Integration tests for the daily tarot pipeline (ISSUE-049).

Covers the full happy-path + idempotency contract:

1. ``POST /api/v1/tarot/today/flip`` with a fresh user → 200 with
   ``text/event-stream`` Content-Type, subtitle + audio_ready + end
   events, and one ``tarot_draws`` row.
2. Second call same KST day → returns successfully without creating a
   second row (AC 2 — idempotency on ``(user_or_device, date_kst)``).
3. First ``audio_ready`` event lands within a relaxed test budget; the
   real NFR-003 (≤ 2s first chunk) is instrumented in production via
   OTel spans (see ``run_tarot_pipeline.first_audio_budget_violated``).

These tests use ``MockStorageAdapter(root=tmp_path)`` so chunks land in
a hermetic tmp dir, ``LLM_PROVIDER=mock`` + ``TTS_PROVIDER=mock`` so
the pipeline is deterministic, and ``InMemoryQuotaStore=None`` so
quota reads exercise the DB-scan fallback (architecture §13).
"""

from __future__ import annotations

import asyncio
import base64
import json
import time
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
    Device,
    TarotCard,
    TarotDraw,
    User,
)
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


# ---------------------------------------------------------------------------
# Seed helpers
# ---------------------------------------------------------------------------


async def _seed_22_cards(engine: AsyncEngine) -> None:
    """Mirror migration ``0008_tarot_tables_seed`` for in-memory SQLite."""
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as s:
        for idx in range(22):
            s.add(
                TarotCard(
                    card_index=idx,
                    name_kr=f"메이저-{idx:02d}",
                    name_en=f"Major {idx:02d}",
                    meaning_kr=f"meaning_kr_{idx}",
                    art_key=f"tarot/major/{idx:02d}.webp",
                )
            )
        await s.commit()


async def _seed_user(
    engine: AsyncEngine, *, kakao_sub: str = "kakao-tarot-pipeline-1"
) -> str:
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as s:
        u = User(kakao_sub=kakao_sub)
        s.add(u)
        await s.commit()
        await s.refresh(u)
        return str(u.id)


def _make_client(
    engine: AsyncEngine,
    user_id: str | None,
    *,
    storage_root: Path | None = None,
) -> TestClient:
    maker = async_sessionmaker(engine, expire_on_commit=False)

    async def _override_get_session() -> AsyncIterator[AsyncSession]:
        async with maker() as s:
            yield s

    app = create_app()
    app.dependency_overrides[get_session] = _override_get_session

    if user_id is not None:
        from voicesaju.tarot.routers.today import _get_current_user_id

        app.dependency_overrides[_get_current_user_id] = lambda: user_id

    if storage_root is not None:
        from voicesaju.tarot.routers.today import _get_r2_client

        adapter = MockStorageAdapter(root=storage_root)
        r2 = R2Client(adapter=adapter)
        app.dependency_overrides[_get_r2_client] = lambda: r2

    return TestClient(app)


def _parse_sse_events(raw: str) -> list[tuple[str, dict]]:
    """Parse an SSE blob into a list of ``(event_name, json_data)``."""
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
        if not data_str:
            payload: dict = {}
        else:
            try:
                payload = json.loads(data_str)
            except json.JSONDecodeError:
                payload = {"_raw": data_str}
        events.append((event_name, payload))
    return events


# ---------------------------------------------------------------------------
# Happy path — POST flip → SSE stream → tarot_draws row written.
# ---------------------------------------------------------------------------


def test_flip_streams_subtitle_audio_ready_end_and_writes_draw(
    engine: AsyncEngine, tmp_path: Path
) -> None:
    """Full happy path: SSE events in order + a row in tarot_draws.

    Asserts:
    - 200 + ``text/event-stream`` Content-Type.
    - ``subtitle`` precedes ``audio_ready`` (architecture §6.3 ordering).
    - Stream terminates on an ``end`` event.
    - Exactly one ``tarot_draws`` row exists for the caller.
    - Chunk files exist under ``audio/tarot/{draw_id}/chunks/``.
    """
    asyncio.run(_seed_22_cards(engine))
    user_id = asyncio.run(_seed_user(engine))
    client = _make_client(engine, user_id, storage_root=tmp_path)

    with client.stream("POST", "/api/v1/tarot/today/flip") as stream_resp:
        assert stream_resp.status_code == 200, stream_resp.read().decode("utf-8")
        assert "text/event-stream" in stream_resp.headers.get("content-type", "")
        chunks: list[bytes] = []
        for chunk in stream_resp.iter_bytes():
            chunks.append(chunk)
    raw = b"".join(chunks).decode("utf-8")

    events = _parse_sse_events(raw)
    assert events, f"no SSE events parsed; raw head={raw[:400]!r}"
    event_names = [name for name, _ in events]

    assert "subtitle" in event_names, event_names
    assert "audio_ready" in event_names, event_names
    assert event_names[-1] == "end", event_names

    # Ordering — subtitle MUST precede the first audio_ready event so
    # the frontend's playhead scheduler can set up before the chunk URL
    # is fetchable.
    first_subtitle = event_names.index("subtitle")
    first_audio = event_names.index("audio_ready")
    assert first_subtitle < first_audio, event_names

    # Each subtitle carries text + audio_offset_ms; each audio_ready
    # carries seq + url. Sanity-check the contract.
    subtitle_events = [d for n, d in events if n == "subtitle"]
    for data in subtitle_events:
        assert "text" in data and isinstance(data["text"], str)
        assert "audio_offset_ms" in data and isinstance(data["audio_offset_ms"], int)
    audio_events = [d for n, d in events if n == "audio_ready"]
    for data in audio_events:
        assert "seq" in data and isinstance(data["seq"], int)
        assert "url" in data and data["url"]

    # Terminal ``end`` event carries draw_id + duration_ms.
    end_event = events[-1][1]
    assert "draw_id" in end_event, end_event
    draw_id = end_event["draw_id"]
    assert "duration_ms" in end_event

    # DB state — exactly one tarot_draws row for this user.
    maker = async_sessionmaker(engine, expire_on_commit=False)

    async def _count_and_fetch() -> tuple[int, TarotDraw]:
        async with maker() as s:
            count = (
                await s.execute(
                    select(func.count(TarotDraw.id)).where(TarotDraw.user_id == user_id)
                )
            ).scalar_one()
            row = (
                await s.execute(select(TarotDraw).where(TarotDraw.user_id == user_id))
            ).scalar_one()
            return int(count), row

    row_count, draw_row = asyncio.run(_count_and_fetch())
    assert row_count == 1, f"expected 1 tarot_draws row, got {row_count}"
    assert str(draw_row.id) == draw_id

    # Chunks landed on disk under the storage root.
    chunk_files = sorted(
        (tmp_path / "audio" / "tarot" / draw_id / "chunks").glob("*.mp3")
    )
    assert (
        len(chunk_files) >= 1
    ), f"expected ≥1 chunk under storage root, found {chunk_files}"


# ---------------------------------------------------------------------------
# AC 2 — idempotency: same user, same KST day → one row only.
# ---------------------------------------------------------------------------


def test_flip_is_idempotent_same_day(engine: AsyncEngine, tmp_path: Path) -> None:
    """AC 2: two POSTs same KST day → exactly one tarot_draws row.

    The second POST MUST succeed (return 200 with the same draw_id) so
    the client can replay the audio for the day's already-flipped card
    rather than seeing a 4xx mid-ritual.
    """
    asyncio.run(_seed_22_cards(engine))
    user_id = asyncio.run(_seed_user(engine, kakao_sub="kakao-tarot-idemp"))
    client = _make_client(engine, user_id, storage_root=tmp_path)

    # First flip — consume the stream to completion.
    with client.stream("POST", "/api/v1/tarot/today/flip") as r1:
        assert r1.status_code == 200
        raw1 = b"".join(r1.iter_bytes()).decode("utf-8")
    events1 = _parse_sse_events(raw1)
    end1 = events1[-1][1]
    draw_id_1 = end1["draw_id"]

    # Second flip — same user, same KST day → MUST reuse the existing
    # draw row (no second insert).
    with client.stream("POST", "/api/v1/tarot/today/flip") as r2:
        assert r2.status_code == 200
        raw2 = b"".join(r2.iter_bytes()).decode("utf-8")
    events2 = _parse_sse_events(raw2)
    end2 = events2[-1][1]
    draw_id_2 = end2["draw_id"]

    assert draw_id_1 == draw_id_2, (
        f"second flip returned a different draw_id ({draw_id_1} vs "
        f"{draw_id_2}) — idempotency broken"
    )

    # DB sanity — exactly one row, despite two POSTs.
    maker = async_sessionmaker(engine, expire_on_commit=False)

    async def _count_rows() -> int:
        async with maker() as s:
            return int(
                (
                    await s.execute(
                        select(func.count(TarotDraw.id)).where(
                            TarotDraw.user_id == user_id
                        )
                    )
                ).scalar_one()
            )

    assert asyncio.run(_count_rows()) == 1


# ---------------------------------------------------------------------------
# AC 4 — first audio_ready event arrives inside a relaxed test budget.
# ---------------------------------------------------------------------------


def test_first_audio_ready_arrives_within_test_budget(
    engine: AsyncEngine, tmp_path: Path
) -> None:
    """NFR-003: production first-audio budget is 2s; test budget is 7.5s.

    Starlette TestClient buffers SSE chunks until the response generator
    finishes, so wall-clock measurements here are dominated by the
    full mock pipeline (LLM sentence pacing + TTS chunk pacing) rather
    than the actual time-to-first-chunk that production uvicorn emits.

    Mirrors the test-budget pattern from
    ``tests/unit/reading/test_pipeline_timing.py``: the real NFR-003
    check is the OTel span ``tarot_pipeline.first_audio_budget_violated``
    emitted in production code; this test just guards against
    catastrophic regressions (e.g. a pipeline that takes 30s).
    """
    asyncio.run(_seed_22_cards(engine))
    user_id = asyncio.run(_seed_user(engine, kakao_sub="kakao-tarot-timing"))
    client = _make_client(engine, user_id, storage_root=tmp_path)

    started = time.perf_counter()
    first_audio_at: float | None = None
    buffer = ""
    with client.stream("POST", "/api/v1/tarot/today/flip") as stream_resp:
        assert stream_resp.status_code == 200
        for chunk in stream_resp.iter_bytes():
            buffer += chunk.decode("utf-8", errors="ignore")
            if first_audio_at is None and "event: audio_ready" in buffer:
                first_audio_at = time.perf_counter()
            if time.perf_counter() - started > 12.0:
                break

    assert (
        first_audio_at is not None
    ), f"never saw audio_ready event; buffer head={buffer[:400]!r}"
    elapsed = first_audio_at - started
    # 7.5s mirrors ``test_pipeline_timing.py`` budget — the production
    # NFR-003 budget is 2.0s, enforced via OTel instrumentation, not
    # via this test (see module docstring).
    assert elapsed < 7.5, (
        f"first audio_ready arrived after {elapsed:.3f}s "
        f"(test budget < 7.5s; production NFR-003 budget is 2.0s)"
    )
