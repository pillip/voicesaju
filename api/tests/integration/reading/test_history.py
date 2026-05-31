"""Integration tests for the history list + audio replay endpoints (ISSUE-066).

Covers AC1/2/3 for ISSUE-066:

- AC1: archived audio for a past reading is served from the storage
  adapter without re-running the LLM pipeline.
- AC2: the row's audio blob missing in storage → 410 Gone with the
  expired-audio error code (frontend renders the fallback copy).
- AC3: pause is a frontend-only concern, but the route must return a
  full-body response with ``Content-Type: audio/mpeg`` so the
  ``<audio>`` element can seek/pause natively.

Plus list-endpoint coverage:

- Pagination (?page=1) returns 20 rows desc by started_at.
- Empty list when the caller has no readings.
- Scoping — other users' readings never appear.

Architecture-Ref: §6.3. PRD-Ref: FR-028, US-16.
"""

from __future__ import annotations

import asyncio
import base64
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from voicesaju.adapters.storage import MockStorageAdapter
from voicesaju.db.base import Base
from voicesaju.db.engine import get_session
from voicesaju.db.models.reading_audio import ReadingAudio
from voicesaju.db.models.reading_transcripts import ReadingTranscript
from voicesaju.db.models.readings import Reading
from voicesaju.db.models.users import User
from voicesaju.main import create_app
from voicesaju.storage.r2_client import R2Client


@pytest.fixture(autouse=True)
def _env_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    """Minimum env so ``create_app()`` boots without real creds."""
    fake_kek = base64.b64encode(b"\x00" * 32).decode("ascii")
    monkeypatch.setenv("LOCAL_KEK_BASE64", fake_kek)
    monkeypatch.setenv("KMS_PROVIDER", "local")
    monkeypatch.setenv("PAYMENT_PROVIDER", "mock")
    monkeypatch.setenv("STORAGE_PROVIDER", "mock")


@pytest_asyncio.fixture
async def engine() -> AsyncIterator[AsyncEngine]:
    eng = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    await eng.dispose()


async def _seed_user(engine: AsyncEngine, kakao_sub: str = "history-1") -> str:
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as s:
        u = User(kakao_sub=kakao_sub)
        s.add(u)
        await s.commit()
        await s.refresh(u)
        return str(u.id)


async def _seed_payment_for_entitlement(engine: AsyncEngine, user_id: str) -> str:
    """Insert a paid Payment so readings have a valid ``payment_id``.

    The Reading model's CHECK constraint requires exactly one of
    payment_id / subscription_id / free_token_id to be set; we use
    ``payment`` everywhere in this suite to keep the fixture simple.
    """
    from voicesaju.db.models.payments import Payment

    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as s:
        p = Payment(
            user_id=user_id,
            kind="single",
            amount_krw=4900,
            method="tosspay",
            status="paid",
            paid_at=datetime(2026, 1, 1, tzinfo=UTC),
            toss_order_id=f"toss-seed-{user_id[:8]}",
        )
        s.add(p)
        await s.commit()
        await s.refresh(p)
        return str(p.id)


async def _seed_readings(
    engine: AsyncEngine,
    *,
    user_id: str,
    payment_id: str,
    count: int,
    with_audio: bool = True,
    with_transcript: bool = True,
) -> list[str]:
    """Insert ``count`` complete readings with ascending ``started_at``.

    Returns IDs in descending started_at order so test expectations
    match the API's response ordering without re-sorting.
    """
    maker = async_sessionmaker(engine, expire_on_commit=False)
    base = datetime(2026, 1, 1, tzinfo=UTC)
    ids: list[str] = []
    async with maker() as s:
        for i in range(count):
            r = Reading(
                user_id=user_id,
                category="love",
                status="complete",
                character_key="nuna",
                entitlement_kind="payment",
                payment_id=payment_id,
                started_at=base + timedelta(minutes=i),
                completed_at=base + timedelta(minutes=i, seconds=90),
            )
            s.add(r)
            await s.commit()
            await s.refresh(r)
            ids.append(str(r.id))

            if with_audio:
                # Real r2_key — the audio endpoint test exercises a
                # subset of these (we populate the MockStorageAdapter
                # for the first one only).
                a = ReadingAudio(
                    reading_id=r.id,
                    r2_url=f"mock://audio/readings/{r.id}/main.mp3",
                    r2_key=f"audio/readings/{r.id}/main.mp3",
                    duration_ms=90_000,
                    content_hash="a" * 64,
                    file_size_bytes=12345,
                )
                s.add(a)
                await s.commit()

            if with_transcript:
                t = ReadingTranscript(
                    reading_id=r.id,
                    transcript_text=(f"별기운이 좋네. 이번 달은 사랑운이 풀려. (#{i})"),
                    model_name="claude-3-7-sonnet@phase1",
                )
                s.add(t)
                await s.commit()

    # Desc by started_at == reverse of insertion order.
    return list(reversed(ids))


def _make_client(
    engine: AsyncEngine,
    user_id: str | None,
    *,
    r2: R2Client | None = None,
) -> TestClient:
    """Build a TestClient with overridden auth dep + session + R2."""
    maker = async_sessionmaker(engine, expire_on_commit=False)

    async def _override_get_session() -> AsyncIterator[AsyncSession]:
        async with maker() as s:
            yield s

    app = create_app()
    app.dependency_overrides[get_session] = _override_get_session

    from voicesaju.readings.routers.history import (
        _get_current_user_id,
        _get_r2_client,
    )

    if user_id is not None:
        app.dependency_overrides[_get_current_user_id] = lambda: user_id
    if r2 is not None:
        app.dependency_overrides[_get_r2_client] = lambda: r2
    return TestClient(app)


# ---------------------------------------------------------------------------
# GET /api/v1/me/readings — list
# ---------------------------------------------------------------------------


def test_list_returns_first_page_desc_with_pagination(engine: AsyncEngine) -> None:
    """AC: 25 readings + ``?page=1`` → 20 rows desc by started_at."""
    user_id = asyncio.run(_seed_user(engine))
    payment_id = asyncio.run(_seed_payment_for_entitlement(engine, user_id))
    expected_desc_ids = asyncio.run(
        _seed_readings(engine, user_id=user_id, payment_id=payment_id, count=25)
    )

    client = _make_client(engine, user_id=user_id)
    resp = client.get("/api/v1/me/readings?page=1")

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert isinstance(body, list)
    assert len(body) == 20
    assert [row["id"] for row in body] == expected_desc_ids[:20]
    # AC: audio_available is True when the audio row was inserted with
    # a non-null r2_key.
    assert all(row["audio_available"] is True for row in body)
    # AC: summary is populated from the transcript.
    assert all(row["summary"] for row in body)


def test_list_empty_for_user_with_no_readings(engine: AsyncEngine) -> None:
    """AC: 0 readings → ``[]``."""
    user_id = asyncio.run(_seed_user(engine))
    client = _make_client(engine, user_id=user_id)

    resp = client.get("/api/v1/me/readings")
    assert resp.status_code == 200
    assert resp.json() == []


def test_list_scopes_to_caller_only(engine: AsyncEngine) -> None:
    """Other users' readings must never appear in the response."""
    user_a = asyncio.run(_seed_user(engine, "history-a"))
    user_b = asyncio.run(_seed_user(engine, "history-b"))
    pay_a = asyncio.run(_seed_payment_for_entitlement(engine, user_a))
    pay_b = asyncio.run(_seed_payment_for_entitlement(engine, user_b))
    a_ids = asyncio.run(
        _seed_readings(engine, user_id=user_a, payment_id=pay_a, count=3)
    )
    asyncio.run(_seed_readings(engine, user_id=user_b, payment_id=pay_b, count=5))

    client = _make_client(engine, user_id=user_a)
    resp = client.get("/api/v1/me/readings")

    assert resp.status_code == 200
    ids = {row["id"] for row in resp.json()}
    assert ids == set(a_ids)


def test_list_requires_auth(engine: AsyncEngine) -> None:
    """Anonymous calls → 401."""
    client = _make_client(engine, user_id=None)
    resp = client.get("/api/v1/me/readings")
    assert resp.status_code == 401


def test_list_audio_available_false_when_no_audio_row(
    engine: AsyncEngine,
) -> None:
    """``audio_available`` reflects DB-level presence of r2_key."""
    user_id = asyncio.run(_seed_user(engine))
    payment_id = asyncio.run(_seed_payment_for_entitlement(engine, user_id))
    asyncio.run(
        _seed_readings(
            engine,
            user_id=user_id,
            payment_id=payment_id,
            count=1,
            with_audio=False,
            with_transcript=False,
        )
    )

    client = _make_client(engine, user_id=user_id)
    resp = client.get("/api/v1/me/readings")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["audio_available"] is False
    assert body[0]["summary"] is None


# ---------------------------------------------------------------------------
# GET /api/v1/reading/{id}/audio.mp3 — replay
# ---------------------------------------------------------------------------


def test_audio_returns_archived_blob(engine: AsyncEngine, tmp_path) -> None:
    """AC1: past reading streams archived audio without regeneration."""
    user_id = asyncio.run(_seed_user(engine))
    payment_id = asyncio.run(_seed_payment_for_entitlement(engine, user_id))
    ids = asyncio.run(
        _seed_readings(engine, user_id=user_id, payment_id=payment_id, count=1)
    )
    reading_id = ids[0]

    # Stage the archived blob in the mock storage at the row's r2_key.
    adapter = MockStorageAdapter(root=tmp_path)
    key = f"audio/readings/{reading_id}/main.mp3"
    payload = b"\xff\xfb\x90\x00archived-audio-bytes"
    asyncio.run(adapter.put_object(key, payload))
    r2 = R2Client(adapter=adapter)

    client = _make_client(engine, user_id=user_id, r2=r2)
    resp = client.get(f"/api/v1/reading/{reading_id}/audio.mp3")

    assert resp.status_code == 200, resp.text
    assert resp.headers["content-type"] == "audio/mpeg"
    assert resp.headers.get("accept-ranges") == "bytes"
    assert resp.content == payload


def test_audio_returns_410_when_blob_missing(engine: AsyncEngine, tmp_path) -> None:
    """AC2: blob missing in storage → 410 with ``audio_expired`` code."""
    user_id = asyncio.run(_seed_user(engine))
    payment_id = asyncio.run(_seed_payment_for_entitlement(engine, user_id))
    ids = asyncio.run(
        _seed_readings(engine, user_id=user_id, payment_id=payment_id, count=1)
    )
    reading_id = ids[0]

    # No staging — the adapter does not have the blob.
    r2 = R2Client(adapter=MockStorageAdapter(root=tmp_path))
    client = _make_client(engine, user_id=user_id, r2=r2)

    resp = client.get(f"/api/v1/reading/{reading_id}/audio.mp3")
    assert resp.status_code == 410
    body = resp.json()
    # FastAPI wraps the ``detail`` key around our dict.
    assert body["detail"]["error"]["code"] == "audio_expired"
    assert "재생할 수 없습니다" in body["detail"]["error"]["message"]


def test_audio_returns_410_when_audio_row_absent(engine: AsyncEngine, tmp_path) -> None:
    """A reading without an audio row also surfaces as 410 (expired)."""
    user_id = asyncio.run(_seed_user(engine))
    payment_id = asyncio.run(_seed_payment_for_entitlement(engine, user_id))
    ids = asyncio.run(
        _seed_readings(
            engine,
            user_id=user_id,
            payment_id=payment_id,
            count=1,
            with_audio=False,
            with_transcript=False,
        )
    )
    reading_id = ids[0]

    r2 = R2Client(adapter=MockStorageAdapter(root=tmp_path))
    client = _make_client(engine, user_id=user_id, r2=r2)

    resp = client.get(f"/api/v1/reading/{reading_id}/audio.mp3")
    assert resp.status_code == 410
    assert resp.json()["detail"]["error"]["code"] == "audio_expired"


def test_audio_returns_404_for_foreign_reading(engine: AsyncEngine, tmp_path) -> None:
    """Another user's reading must surface as 404 (not 403)."""
    user_a = asyncio.run(_seed_user(engine, "history-a"))
    user_b = asyncio.run(_seed_user(engine, "history-b"))
    pay_b = asyncio.run(_seed_payment_for_entitlement(engine, user_b))
    b_ids = asyncio.run(
        _seed_readings(engine, user_id=user_b, payment_id=pay_b, count=1)
    )
    foreign_id = b_ids[0]

    r2 = R2Client(adapter=MockStorageAdapter(root=tmp_path))
    client = _make_client(engine, user_id=user_a, r2=r2)

    resp = client.get(f"/api/v1/reading/{foreign_id}/audio.mp3")
    assert resp.status_code == 404


def test_audio_returns_etag_when_content_hash_present(
    engine: AsyncEngine, tmp_path
) -> None:
    """ETag is rendered from the persisted ``content_hash``."""
    user_id = asyncio.run(_seed_user(engine))
    payment_id = asyncio.run(_seed_payment_for_entitlement(engine, user_id))
    ids = asyncio.run(
        _seed_readings(engine, user_id=user_id, payment_id=payment_id, count=1)
    )
    reading_id = ids[0]

    adapter = MockStorageAdapter(root=tmp_path)
    key = f"audio/readings/{reading_id}/main.mp3"
    asyncio.run(adapter.put_object(key, b"\xff\xfbx"))
    r2 = R2Client(adapter=adapter)

    client = _make_client(engine, user_id=user_id, r2=r2)
    resp = client.get(f"/api/v1/reading/{reading_id}/audio.mp3")

    assert resp.status_code == 200
    assert resp.headers["etag"] == f'"{"a" * 64}"'


def test_audio_requires_auth(engine: AsyncEngine) -> None:
    """Anonymous audio fetch → 401."""
    client = _make_client(engine, user_id=None)
    resp = client.get("/api/v1/reading/anything/audio.mp3")
    assert resp.status_code == 401
