"""Integration tests for the payments history endpoint (ISSUE-073).

Covers:

- AC1: 25 payments + ``?page=1`` → 20 rows, sorted by ``created_at DESC``.
- AC2: 0 payments → ``[]``.

Architecture-Ref: §6.5. PRD-Ref: FR-026, US-12.
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

from voicesaju.db.base import Base
from voicesaju.db.engine import get_session
from voicesaju.db.models.payments import Payment
from voicesaju.db.models.users import User
from voicesaju.main import create_app


@pytest.fixture(autouse=True)
def _env_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    """Minimum env so `create_app()` boots without real KMS/Toss creds."""
    fake_kek = base64.b64encode(b"\x00" * 32).decode("ascii")
    monkeypatch.setenv("LOCAL_KEK_BASE64", fake_kek)
    monkeypatch.setenv("KMS_PROVIDER", "local")
    monkeypatch.setenv("PAYMENT_PROVIDER", "mock")


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


async def _seed_payments(
    engine: AsyncEngine,
    *,
    user_id: str,
    count: int,
    base_amount_krw: int = 4900,
) -> list[str]:
    """Insert ``count`` paid Payment rows with ascending ``created_at``.

    Returns the payment ids in **descending** ``created_at`` order so that
    the test's expected sort matches the API's response ordering without
    re-sorting at the test side.
    """
    maker = async_sessionmaker(engine, expire_on_commit=False)
    base = datetime(2026, 1, 1, tzinfo=UTC)
    ids: list[str] = []
    async with maker() as s:
        for i in range(count):
            p = Payment(
                user_id=user_id,
                kind="single",
                amount_krw=base_amount_krw + i,
                method="tosspay",
                status="paid",
                paid_at=base + timedelta(minutes=i),
                toss_order_id=f"toss-{user_id[:8]}-{i:03d}",
                created_at=base + timedelta(minutes=i),  # type: ignore[arg-type]
            )
            s.add(p)
            await s.commit()
            await s.refresh(p)
            ids.append(str(p.id))
    # Descending by created_at == reverse of insertion order.
    return list(reversed(ids))


def _make_client(engine: AsyncEngine, user_id: str | None) -> TestClient:
    """Build a TestClient with an overridden auth dep + session."""
    maker = async_sessionmaker(engine, expire_on_commit=False)

    async def _override_get_session() -> AsyncIterator[AsyncSession]:
        async with maker() as s:
            yield s

    app = create_app()
    app.dependency_overrides[get_session] = _override_get_session

    from voicesaju.payment.history import _get_current_user_id

    if user_id is not None:
        app.dependency_overrides[_get_current_user_id] = lambda: user_id
    return TestClient(app)


def test_history_returns_first_page_with_20_rows_desc(engine: AsyncEngine) -> None:
    """AC1: with 25 paid payments, ``?page=1`` returns 20 rows desc."""
    user_id = asyncio.run(_seed_user(engine))
    expected_desc_ids = asyncio.run(_seed_payments(engine, user_id=user_id, count=25))
    client = _make_client(engine, user_id)

    resp = client.get("/api/v1/payments/history?page=1")
    assert resp.status_code == 200, resp.text
    rows = resp.json()
    assert isinstance(rows, list)
    assert len(rows) == 20

    # IDs are the 20 newest, in descending created_at order.
    assert [row["id"] for row in rows] == expected_desc_ids[:20]

    # Required fields per AC: id, type/kind, amount_krw, status, paid_at,
    # refunded_amount_krw. The 'category' key is reserved for the row's
    # business category (we map saju category at render time; for now expose
    # the discriminator the issue calls out).
    first = rows[0]
    for field in (
        "id",
        "type",
        "amount_krw",
        "status",
        "paid_at",
        "refunded_amount_krw",
    ):
        assert field in first, f"missing field {field!r} in response"


def test_history_returns_second_page(engine: AsyncEngine) -> None:
    """Page 2 with 25 payments → 5 trailing rows."""
    user_id = asyncio.run(_seed_user(engine))
    expected_desc_ids = asyncio.run(_seed_payments(engine, user_id=user_id, count=25))
    client = _make_client(engine, user_id)

    resp = client.get("/api/v1/payments/history?page=2")
    assert resp.status_code == 200, resp.text
    rows = resp.json()
    assert len(rows) == 5
    assert [row["id"] for row in rows] == expected_desc_ids[20:25]


def test_history_empty_for_user_with_no_payments(engine: AsyncEngine) -> None:
    """AC2: 0 payments → ``[]``."""
    user_id = asyncio.run(_seed_user(engine))
    client = _make_client(engine, user_id)

    resp = client.get("/api/v1/payments/history")
    assert resp.status_code == 200, resp.text
    assert resp.json() == []


def test_history_is_scoped_to_caller(engine: AsyncEngine) -> None:
    """Caller's history must not include other users' payments."""
    user_a = asyncio.run(_seed_user(engine, kakao_sub="a"))
    user_b = asyncio.run(_seed_user(engine, kakao_sub="b"))
    asyncio.run(_seed_payments(engine, user_id=user_a, count=3))
    asyncio.run(_seed_payments(engine, user_id=user_b, count=2))

    client = _make_client(engine, user_a)
    rows = client.get("/api/v1/payments/history").json()
    assert len(rows) == 3


def test_history_requires_authentication(engine: AsyncEngine) -> None:
    """Anonymous callers get 401 — the endpoint never returns other users' rows."""
    # No auth override → the real dep raises 401 from `request.state.user`.
    client = _make_client(engine, user_id=None)
    resp = client.get("/api/v1/payments/history")
    assert resp.status_code == 401


def test_history_rejects_invalid_page(engine: AsyncEngine) -> None:
    """``?page=0`` or negative → 422 (FastAPI validation)."""
    user_id = asyncio.run(_seed_user(engine))
    client = _make_client(engine, user_id)

    resp = client.get("/api/v1/payments/history?page=0")
    assert resp.status_code == 422
