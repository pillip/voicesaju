"""Integration tests for ``GET /api/v1/reading/intro/{category}`` (ISSUE-031).

Exercises the intro-clip lookup endpoint end-to-end via FastAPI's
``TestClient`` against an in-memory SQLite engine. Mirrors the test
fixtures in ``tests/integration/profile/test_create_profile.py``:

* The schema is created by reflecting all ``Base.metadata`` tables; the
  alembic seed migration is NOT run, so each test that needs intro clips
  inserts them via the ORM directly.
* Auth is injected by overriding the route's
  ``_get_current_user_id`` dependency rather than minting a JWT.

AC coverage (mirrors ISSUE-031 spec):
- ``category=love`` + caller ``birth_time_known=true`` → ``known`` variant
  clip URL is returned with subtitle + duration_ms.
- ``birth_time_known=false`` → ``unknown`` variant URL is returned.
- No clip seeded for the category → 404.
- No auth → 401.
"""

from __future__ import annotations

import asyncio
import base64
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from voicesaju.db.base import Base
from voicesaju.db.engine import get_session
from voicesaju.db.models import IntroAudioClip, Profile, User  # noqa: F401
from voicesaju.main import create_app


@pytest.fixture(autouse=True)
def _local_kek_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Provide a deterministic ``LocalKMS`` for envelope encryption.

    ``profiles.birth_dt`` is envelope-encrypted on insert. The model
    setter calls ``envelope.encrypt_field`` which reads
    ``LOCAL_KEK_BASE64`` from the environment.
    """
    fake_kek = base64.b64encode(b"\x00" * 32).decode("ascii")
    monkeypatch.setenv("LOCAL_KEK_BASE64", fake_kek)
    monkeypatch.setenv("KMS_PROVIDER", "local")


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


async def _seed_user_and_profile(
    engine: AsyncEngine,
    *,
    birth_time_known: bool,
    kakao_sub: str = "kakao-intro-1",
) -> str:
    """Insert a user + matching profile and return the user_id."""
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as s:
        u = User(kakao_sub=kakao_sub)
        s.add(u)
        await s.commit()
        await s.refresh(u)

        p = Profile(
            user_id=u.id,
            birth_time_known=birth_time_known,
            birth_is_lunar=False,
        )
        # birth_dt is envelope-encrypted on assignment via the setter,
        # which expects a *string* plaintext form (see profile router
        # ``_format_birth_dt_plaintext``).
        p.birth_dt = "1997-08-13T07:30"
        s.add(p)
        await s.commit()
        return str(u.id)


async def _seed_intro_clip(
    engine: AsyncEngine,
    *,
    category: str,
    birth_time_variant: str,
    r2_url: str | None = None,
    duration_ms: int = 15000,
    character_key: str = "nuna",
) -> None:
    """Insert a single ``intro_audio_clips`` row."""
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as s:
        clip = IntroAudioClip(
            category=category,
            birth_time_variant=birth_time_variant,
            character_key=character_key,
            r2_url=r2_url or f"tts/intro/{category}/{birth_time_variant}.mp3",
            duration_ms=duration_ms,
        )
        s.add(clip)
        await s.commit()


def _make_client(engine: AsyncEngine, user_id: str | None) -> TestClient:
    """Build a TestClient with DB override and (optional) auth override."""
    maker = async_sessionmaker(engine, expire_on_commit=False)

    async def _override_get_session() -> AsyncIterator[AsyncSession]:
        async with maker() as s:
            yield s

    app = create_app()
    app.dependency_overrides[get_session] = _override_get_session

    if user_id is not None:
        from voicesaju.readings.routers.intro import _get_current_user_id

        app.dependency_overrides[_get_current_user_id] = lambda: user_id

    return TestClient(app)


# ---------------------------------------------------------------------------
# AC 1 — known variant
# ---------------------------------------------------------------------------


def test_get_intro_returns_known_variant_when_birth_time_known(
    engine: AsyncEngine,
) -> None:
    """AC: ``birth_time_known=true`` → returns the ``known`` variant clip.

    The profile carries ``birth_time_known=True`` and the test seeds both
    variants for ``love``. The route must pick ``known`` and return its
    fields exactly.
    """
    user_id = asyncio.run(
        _seed_user_and_profile(engine, birth_time_known=True, kakao_sub="kakao-known")
    )
    asyncio.run(
        _seed_intro_clip(
            engine,
            category="love",
            birth_time_variant="known",
            r2_url="tts/intro/love/known.mp3",
            duration_ms=15000,
        )
    )
    asyncio.run(
        _seed_intro_clip(
            engine,
            category="love",
            birth_time_variant="unknown",
            r2_url="tts/intro/love/unknown.mp3",
            duration_ms=17000,
        )
    )

    client = _make_client(engine, user_id)
    resp = client.get("/api/v1/reading/intro/love")

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["audio_url"] == "tts/intro/love/known.mp3"
    assert body["duration_ms"] == 15000
    # Subtitle must be a non-empty string; exact copy is documented in
    # the route module so we just assert the contract here.
    assert isinstance(body["subtitle"], str) and body["subtitle"]


# ---------------------------------------------------------------------------
# AC 2 — unknown variant
# ---------------------------------------------------------------------------


def test_get_intro_returns_unknown_variant_when_birth_time_unknown(
    engine: AsyncEngine,
) -> None:
    """AC: ``birth_time_known=false`` → returns the ``unknown`` variant."""
    user_id = asyncio.run(
        _seed_user_and_profile(
            engine, birth_time_known=False, kakao_sub="kakao-unknown"
        )
    )
    asyncio.run(
        _seed_intro_clip(
            engine,
            category="love",
            birth_time_variant="known",
            r2_url="tts/intro/love/known.mp3",
            duration_ms=15000,
        )
    )
    asyncio.run(
        _seed_intro_clip(
            engine,
            category="love",
            birth_time_variant="unknown",
            r2_url="tts/intro/love/unknown.mp3",
            duration_ms=17000,
        )
    )

    client = _make_client(engine, user_id)
    resp = client.get("/api/v1/reading/intro/love")

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["audio_url"] == "tts/intro/love/unknown.mp3"
    assert body["duration_ms"] == 17000
    # Subtitle copy for the unknown variant should reference the
    # "시간을 모르면..." help text from copy_guide.md §3.
    assert "시간" in body["subtitle"]


# ---------------------------------------------------------------------------
# AC 3 — 404 when no clip seeded for the category
# ---------------------------------------------------------------------------


def test_get_intro_returns_404_when_no_clip_for_category(
    engine: AsyncEngine,
) -> None:
    """AC: no clip seeded for the requested category → 404."""
    user_id = asyncio.run(
        _seed_user_and_profile(engine, birth_time_known=True, kakao_sub="kakao-404")
    )
    # Seed a clip for ``love`` only; query for ``work`` which has none.
    asyncio.run(
        _seed_intro_clip(
            engine,
            category="love",
            birth_time_variant="known",
        )
    )

    client = _make_client(engine, user_id)
    resp = client.get("/api/v1/reading/intro/work")
    assert resp.status_code == 404, resp.text


# ---------------------------------------------------------------------------
# AC 4 — 401 when no auth
# ---------------------------------------------------------------------------


def test_get_intro_requires_authentication(engine: AsyncEngine) -> None:
    """No auth override → 401 (anonymous callers are rejected)."""
    asyncio.run(
        _seed_intro_clip(
            engine,
            category="love",
            birth_time_variant="known",
        )
    )

    client = _make_client(engine, user_id=None)
    resp = client.get("/api/v1/reading/intro/love")
    assert resp.status_code == 401, resp.text


# ---------------------------------------------------------------------------
# Edge — user has no profile yet → 401 (or similar)
# ---------------------------------------------------------------------------


def test_get_intro_404s_when_user_has_no_profile(engine: AsyncEngine) -> None:
    """If the authenticated user has no profile, we cannot infer
    ``birth_time_known``. The route must reject rather than silently
    pick a default variant.

    Spec: returns 404 (the architecture treats "no profile" as
    equivalent to "no clip available for this caller") — frontend
    handles the fallback per ux_spec.
    """
    # Seed a user but NOT a profile.
    maker = async_sessionmaker(engine, expire_on_commit=False)

    async def _seed() -> str:
        async with maker() as s:
            u = User(kakao_sub="kakao-no-profile")
            s.add(u)
            await s.commit()
            await s.refresh(u)
            return str(u.id)

    user_id = asyncio.run(_seed())
    asyncio.run(
        _seed_intro_clip(
            engine,
            category="love",
            birth_time_variant="known",
        )
    )

    client = _make_client(engine, user_id)
    resp = client.get("/api/v1/reading/intro/love")
    assert resp.status_code == 404, resp.text
