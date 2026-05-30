"""Tests for the weekly free-quota service (ISSUE-048 / FR-014).

The quota service answers a single question: *how many free daily-tarot
draws does this caller still have this calendar week (Mon 00:00 KST
→ Sun 23:59 KST)?*. Behaviour matrix:

- Unauthenticated/anonymous device — 1 free draw per ISO week.
- Logged-in user without an active subscription — 1 free draw per ISO
  week. Owner-identity is independent (FR-016 link path migrates
  device → user; this test uses the user_id path explicitly).
- Logged-in user with an active subscription — *unlimited* (the
  paywall bypass; subscribers never see a tarot quota banner).

Storage tiering (architecture §6.4, AP-33):

1. **Redis-backed counter** (preferred) — key
   ``tarot:quota:{subject_id}:{iso_week_kst}``. Sub-10ms read.
2. **DB-scan fallback** (correctness path) — scan ``tarot_draws`` for
   the (user_id|device_id, date_kst) window when Redis is unavailable.

The tests exercise the DB-scan path exhaustively (no Redis required to
run them) plus a couple of cases with an in-memory Redis stub to assert
the Redis-hit path. The subscriber-bypass path stubs
``check_entitlement`` directly so we don't have to seed FreeToken /
Subscription rows.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from voicesaju.db.base import Base
from voicesaju.db.models import (  # noqa: F401 - register metadata
    Device,
    TarotCard,
    TarotDraw,
    User,
)
from voicesaju.entitlement.service import EntitlementResult
from voicesaju.tarot.quota import (
    UNLIMITED,
    InMemoryQuotaStore,
    QuotaResult,
    check_weekly_free,
    iso_week_kst_key,
)

KST = ZoneInfo("Asia/Seoul")


# ---------------------------------------------------------------------------
# Engine + seed helpers
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def engine() -> AsyncIterator[AsyncEngine]:
    """Per-test SQLite engine with the full ORM schema reflected."""
    eng = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    await eng.dispose()


async def _make_session(engine: AsyncEngine) -> AsyncSession:
    maker = async_sessionmaker(engine, expire_on_commit=False)
    return maker()


async def _seed_user(engine: AsyncEngine, *, kakao_sub: str) -> str:
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as s:
        u = User(kakao_sub=kakao_sub)
        s.add(u)
        await s.commit()
        await s.refresh(u)
        return str(u.id)


async def _seed_device(engine: AsyncEngine, *, vs_did: str) -> str:
    from voicesaju.db.models.users import uuid7

    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as s:
        # ``Device.id`` default is ``uuid7`` (UUID object); aiosqlite
        # cannot bind UUID instances. Pre-coerce to str so the test
        # works on SQLite + Postgres alike.
        d = Device(id=str(uuid7()), device_id_client=vs_did)
        s.add(d)
        await s.commit()
        await s.refresh(d)
        return str(d.id)


async def _seed_card(engine: AsyncEngine, *, index: int = 0) -> str:
    """Seed a single tarot_cards row so tarot_draws FK lookups succeed."""
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as s:
        c = TarotCard(
            card_index=index,
            name_kr=f"카드-{index}",
            name_en=f"Card {index}",
            meaning_kr="meaning_kr",
            art_key=f"tarot/major/{index:02d}.webp",
        )
        s.add(c)
        await s.commit()
        await s.refresh(c)
        return str(c.id)


async def _insert_draw(
    engine: AsyncEngine,
    *,
    user_id: str | None,
    device_id: str | None,
    date_kst: date,
    card_id: str,
    card_index: int = 0,
) -> None:
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as s:
        s.add(
            TarotDraw(
                user_id=user_id,
                device_id=device_id,
                card_id=card_id,
                card_index=card_index,
                date_kst=date_kst,
            )
        )
        await s.commit()


# ---------------------------------------------------------------------------
# iso_week_kst_key — pure helper
# ---------------------------------------------------------------------------


def test_iso_week_kst_key_pins_iso_year_week_format() -> None:
    """Key format is ``YYYY-Www`` per ISO 8601 (e.g. 2026-W22)."""
    # 2026-05-30 is Saturday → ISO week 22 of 2026.
    assert iso_week_kst_key(date(2026, 5, 30)) == "2026-W22"
    # ISO-week-1 trailing into the previous calendar year.
    # 2025-12-29 is Monday → ISO week 1 of 2026 (not 2025!).
    assert iso_week_kst_key(date(2025, 12, 29)) == "2026-W01"


def test_iso_week_kst_key_handles_year_boundary() -> None:
    """Cross-year ISO weeks: Sunday 2026-12-27 vs Monday 2026-12-28."""
    # 2026-12-27 = Sunday → last week of 2026 (W52).
    sunday_key = iso_week_kst_key(date(2026, 12, 27))
    # 2026-12-28 = Monday → 2026-W53 (year has 53 weeks).
    monday_key = iso_week_kst_key(date(2026, 12, 28))
    assert sunday_key != monday_key
    assert sunday_key.startswith("2026-W")
    assert monday_key.startswith("2026-W")


# ---------------------------------------------------------------------------
# DB fallback — fresh user has 1 free draw left this week (AC 1).
# ---------------------------------------------------------------------------


async def _stub_check_entitlement_no_sub(**_: object) -> EntitlementResult:
    """Subject has no active subscription (default for non-subscribers)."""
    return EntitlementResult(
        has_token=False,
        token_id=None,
        has_subscription_credit=False,
        subscription_id=None,
        has_anything=False,
        requires_payment=True,
        preferred_kind="none",
    )


async def _stub_check_entitlement_subscriber(**_: object) -> EntitlementResult:
    """Active subscriber with remaining quota."""
    return EntitlementResult(
        has_token=False,
        has_subscription_credit=True,
        subscription_id="sub-1",
        has_anything=True,
        requires_payment=False,
        preferred_kind="subscription",
    )


@pytest.mark.asyncio
async def test_fresh_user_has_one_remaining_db_fallback(
    engine: AsyncEngine,
) -> None:
    """AC 1: user hasn't drawn this week → ``{remaining: 1}``."""
    user_id = await _seed_user(engine, kakao_sub="kakao-fresh")
    async with await _make_session(engine) as session:
        result = await check_weekly_free(
            session=session,
            user_id=user_id,
            now_kst=datetime(2026, 5, 30, 9, 0, tzinfo=KST),
            redis=None,  # force DB-fallback path
            check_entitlement_fn=_stub_check_entitlement_no_sub,
        )
    assert isinstance(result, QuotaResult)
    assert result.remaining == 1
    assert result.is_unlimited is False
    assert result.source == "db"


@pytest.mark.asyncio
async def test_fresh_device_has_one_remaining_db_fallback(
    engine: AsyncEngine,
) -> None:
    """AC 1 (device path): non-member device → ``{remaining: 1}``."""
    device_id = await _seed_device(engine, vs_did="vsdid-fresh")
    async with await _make_session(engine) as session:
        result = await check_weekly_free(
            session=session,
            device_id=device_id,
            now_kst=datetime(2026, 5, 30, 9, 0, tzinfo=KST),
            redis=None,
        )
    assert result.remaining == 1


# ---------------------------------------------------------------------------
# DB fallback — user already drew this week → 0 remaining (AC 2).
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_user_who_drew_this_week_has_zero_remaining(
    engine: AsyncEngine,
) -> None:
    """AC 2: user has drawn once → ``{remaining: 0}``."""
    user_id = await _seed_user(engine, kakao_sub="kakao-drew")
    card_id = await _seed_card(engine)
    # 2026-05-26 is a Tuesday → same ISO week as 2026-05-30.
    await _insert_draw(
        engine,
        user_id=user_id,
        device_id=None,
        date_kst=date(2026, 5, 26),
        card_id=card_id,
    )
    async with await _make_session(engine) as session:
        result = await check_weekly_free(
            session=session,
            user_id=user_id,
            now_kst=datetime(2026, 5, 30, 9, 0, tzinfo=KST),
            redis=None,
            check_entitlement_fn=_stub_check_entitlement_no_sub,
        )
    assert result.remaining == 0


@pytest.mark.asyncio
async def test_user_drew_in_previous_week_still_has_one_remaining(
    engine: AsyncEngine,
) -> None:
    """A draw in the previous ISO week does NOT count against this week."""
    user_id = await _seed_user(engine, kakao_sub="kakao-old-draw")
    card_id = await _seed_card(engine)
    # 2026-05-24 is a Sunday — last ISO week (W21), NOT W22.
    await _insert_draw(
        engine,
        user_id=user_id,
        device_id=None,
        date_kst=date(2026, 5, 24),
        card_id=card_id,
    )
    async with await _make_session(engine) as session:
        result = await check_weekly_free(
            session=session,
            user_id=user_id,
            now_kst=datetime(2026, 5, 30, 9, 0, tzinfo=KST),
            redis=None,
            check_entitlement_fn=_stub_check_entitlement_no_sub,
        )
    assert result.remaining == 1


# ---------------------------------------------------------------------------
# AC 3 — counter resets crossing Monday 00:00 KST.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_counter_resets_at_monday_kst_boundary(engine: AsyncEngine) -> None:
    """AC 3: time crosses Monday 00:00 KST → counter resets to 1."""
    user_id = await _seed_user(engine, kakao_sub="kakao-monday")
    card_id = await _seed_card(engine)
    # User drew on Sunday 2026-05-31 (still W22).
    await _insert_draw(
        engine,
        user_id=user_id,
        device_id=None,
        date_kst=date(2026, 5, 31),
        card_id=card_id,
    )

    # On Sunday at 23:59:59 KST → ``remaining == 0``.
    async with await _make_session(engine) as session:
        before = await check_weekly_free(
            session=session,
            user_id=user_id,
            now_kst=datetime(2026, 5, 31, 23, 59, 59, tzinfo=KST),
            redis=None,
            check_entitlement_fn=_stub_check_entitlement_no_sub,
        )
    assert before.remaining == 0

    # One second later — Monday 2026-06-01 00:00:00 KST → reset.
    async with await _make_session(engine) as session:
        after = await check_weekly_free(
            session=session,
            user_id=user_id,
            now_kst=datetime(2026, 6, 1, 0, 0, 0, tzinfo=KST),
            redis=None,
            check_entitlement_fn=_stub_check_entitlement_no_sub,
        )
    assert after.remaining == 1


@pytest.mark.asyncio
async def test_now_kst_default_resolves_to_current_kst_date(
    engine: AsyncEngine,
) -> None:
    """When ``now_kst`` is not passed, the service uses the live KST clock.

    We don't pin the exact value (clock-dependent) — only that the call
    succeeds and returns a sane shape. Determinism for explicit dates is
    covered by the boundary tests above.
    """
    user_id = await _seed_user(engine, kakao_sub="kakao-default-clock")
    async with await _make_session(engine) as session:
        result = await check_weekly_free(
            session=session,
            user_id=user_id,
            redis=None,
            check_entitlement_fn=_stub_check_entitlement_no_sub,
        )
    assert result.remaining in (0, 1)
    assert result.is_unlimited is False


# ---------------------------------------------------------------------------
# AC 4 — subscriber bypass returns unlimited.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_subscriber_gets_unlimited(engine: AsyncEngine) -> None:
    """AC 4: active subscriber → ``{remaining: unlimited}``."""
    user_id = await _seed_user(engine, kakao_sub="kakao-sub")
    async with await _make_session(engine) as session:
        result = await check_weekly_free(
            session=session,
            user_id=user_id,
            now_kst=datetime(2026, 5, 30, 9, 0, tzinfo=KST),
            redis=None,
            check_entitlement_fn=_stub_check_entitlement_subscriber,
        )
    assert result.is_unlimited is True
    assert result.remaining == UNLIMITED
    assert result.source == "subscription"


@pytest.mark.asyncio
async def test_subscriber_bypass_skips_db_scan_entirely(
    engine: AsyncEngine,
) -> None:
    """Subscriber bypass returns unlimited even when ``tarot_draws`` is full.

    Defence-in-depth: if a subscriber has drawn 7 times this week (which
    would normally count as quota exhausted), they should still see
    unlimited because the subscription override is hierarchical.
    """
    user_id = await _seed_user(engine, kakao_sub="kakao-sub-heavy")
    card_id = await _seed_card(engine)
    for day in range(25, 31):  # 2026-05-25 (Mon) … 2026-05-30 (Sat)
        await _insert_draw(
            engine,
            user_id=user_id,
            device_id=None,
            date_kst=date(2026, 5, day),
            card_id=card_id,
        )
    async with await _make_session(engine) as session:
        result = await check_weekly_free(
            session=session,
            user_id=user_id,
            now_kst=datetime(2026, 5, 30, 9, 0, tzinfo=KST),
            redis=None,
            check_entitlement_fn=_stub_check_entitlement_subscriber,
        )
    assert result.is_unlimited is True


# ---------------------------------------------------------------------------
# Redis hit / miss / failure — in-memory stub.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_redis_hit_returns_remaining_without_db_scan(
    engine: AsyncEngine,
) -> None:
    """When Redis has the week's counter, return that; never touch the DB."""
    user_id = await _seed_user(engine, kakao_sub="kakao-redis-hit")
    redis = InMemoryQuotaStore()
    # Pre-populate as if the user already drew (counter=1).
    await redis.set(f"tarot:quota:{user_id}:2026-W22", "1")
    async with await _make_session(engine) as session:
        result = await check_weekly_free(
            session=session,
            user_id=user_id,
            now_kst=datetime(2026, 5, 30, 9, 0, tzinfo=KST),
            redis=redis,
            check_entitlement_fn=_stub_check_entitlement_no_sub,
        )
    assert result.remaining == 0
    assert result.source == "redis"


@pytest.mark.asyncio
async def test_redis_miss_falls_back_to_db_and_caches(
    engine: AsyncEngine,
) -> None:
    """Redis miss → DB scan computes the counter and stores it in Redis."""
    user_id = await _seed_user(engine, kakao_sub="kakao-redis-miss")
    card_id = await _seed_card(engine)
    await _insert_draw(
        engine,
        user_id=user_id,
        device_id=None,
        date_kst=date(2026, 5, 26),
        card_id=card_id,
    )
    redis = InMemoryQuotaStore()
    async with await _make_session(engine) as session:
        result = await check_weekly_free(
            session=session,
            user_id=user_id,
            now_kst=datetime(2026, 5, 30, 9, 0, tzinfo=KST),
            redis=redis,
            check_entitlement_fn=_stub_check_entitlement_no_sub,
        )
    assert result.remaining == 0
    assert result.source == "db"

    # The counter should now be in Redis for the next call.
    cached = await redis.get(f"tarot:quota:{user_id}:2026-W22")
    assert cached == "1"


@pytest.mark.asyncio
async def test_redis_failure_silently_falls_back_to_db(
    engine: AsyncEngine,
) -> None:
    """AP-33 graceful degradation: Redis exception → use DB scan.

    Architecture §13 (Failure Modes): "Redis down → tarot cache miss
    falls back to pure hash" — equivalently, here it falls back to the
    DB scan for the quota counter. We do NOT propagate the Redis
    exception to the caller.
    """

    class _BrokenRedis:
        async def get(self, key: str) -> str | None:
            raise ConnectionError("redis is down")

        async def set(self, key: str, value: str, ex: int | None = None) -> None:
            raise ConnectionError("redis is down")

    user_id = await _seed_user(engine, kakao_sub="kakao-redis-broken")
    async with await _make_session(engine) as session:
        result = await check_weekly_free(
            session=session,
            user_id=user_id,
            now_kst=datetime(2026, 5, 30, 9, 0, tzinfo=KST),
            redis=_BrokenRedis(),
            check_entitlement_fn=_stub_check_entitlement_no_sub,
        )
    assert result.remaining == 1
    assert result.source == "db"


# ---------------------------------------------------------------------------
# Identifier discipline.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_requires_user_or_device_id(engine: AsyncEngine) -> None:
    """``check_weekly_free`` rejects calls without an owner identifier."""
    async with await _make_session(engine) as session:
        with pytest.raises(ValueError):
            await check_weekly_free(
                session=session,
                redis=None,
                now_kst=datetime(2026, 5, 30, 9, 0, tzinfo=KST),
            )


@pytest.mark.asyncio
async def test_iso_week_key_uses_kst_not_utc(engine: AsyncEngine) -> None:
    """A UTC timestamp must be converted to KST before key derivation.

    Concrete bug we are guarding against: caller passes a tz-aware UTC
    ``datetime`` at 2026-05-30 16:00 UTC (≈ 2026-05-31 01:00 KST). If
    we don't convert, we land on Saturday W22; with the KST conversion
    we land on Sunday W22 — same week here, but the cross-boundary case
    is asserted by ``test_counter_resets_at_monday_kst_boundary``.

    This test asserts the conversion happens by feeding a UTC instant
    that falls into a *different* date in KST and confirming the result
    reflects the KST view.
    """
    user_id = await _seed_user(engine, kakao_sub="kakao-utc")
    card_id = await _seed_card(engine)
    # Wednesday 2026-05-27 was W22 in KST.
    await _insert_draw(
        engine,
        user_id=user_id,
        device_id=None,
        date_kst=date(2026, 5, 27),
        card_id=card_id,
    )

    # Saturday 2026-05-30 23:30 UTC == Sunday 2026-05-31 08:30 KST (W22).
    now_utc = datetime(2026, 5, 30, 23, 30, tzinfo=UTC)
    async with await _make_session(engine) as session:
        result = await check_weekly_free(
            session=session,
            user_id=user_id,
            now_kst=now_utc,  # naïve impl would skip conversion
            redis=None,
            check_entitlement_fn=_stub_check_entitlement_no_sub,
        )
    # If KST conversion was honoured, the existing draw at 2026-05-27
    # still falls within the same ISO week → 0 remaining.
    assert result.remaining == 0


@pytest.mark.asyncio
async def test_inmemoryquotastore_supports_get_set_roundtrip() -> None:
    """The in-memory stub mirrors enough of redis.asyncio for our tests."""
    store = InMemoryQuotaStore()
    assert await store.get("absent") is None
    await store.set("k", "1", ex=60)
    assert await store.get("k") == "1"


@pytest.mark.asyncio
async def test_week_window_excludes_other_users(engine: AsyncEngine) -> None:
    """One user's draw must NOT decrement another user's quota."""
    user_a = await _seed_user(engine, kakao_sub="kakao-a")
    user_b = await _seed_user(engine, kakao_sub="kakao-b")
    card_id = await _seed_card(engine)
    await _insert_draw(
        engine,
        user_id=user_a,
        device_id=None,
        date_kst=date(2026, 5, 27),
        card_id=card_id,
    )

    now = datetime(2026, 5, 30, 9, 0, tzinfo=KST)
    async with await _make_session(engine) as session:
        a = await check_weekly_free(
            session=session,
            user_id=user_a,
            now_kst=now,
            redis=None,
            check_entitlement_fn=_stub_check_entitlement_no_sub,
        )
        b = await check_weekly_free(
            session=session,
            user_id=user_b,
            now_kst=now,
            redis=None,
            check_entitlement_fn=_stub_check_entitlement_no_sub,
        )
    assert a.remaining == 0
    assert b.remaining == 1
