"""Weekly free-quota service for daily tarot (ISSUE-048 / FR-014).

Answers a single question for the ``/tarot/today`` route + paywall flow:
*how many free draws does this caller have left this ISO week
(Mon 00:00 KST → Sun 23:59 KST)?*

Decision tree (architecture §6.4):

1. **Subscriber bypass** — caller has an active ``Subscription`` with
   remaining credit → returns ``QuotaResult(unlimited=True)``.
   The paywall is hidden; the quota banner is hidden.
2. **Redis-backed counter** — fast path (sub-10ms per AP-33). The key
   ``tarot:quota:{subject_id}:{iso_week_kst}`` (e.g.
   ``tarot:quota:abc-uuid:2026-W22``) stores the draw count for the
   current ISO week. TTL is set to the rest of the week + 1 day buffer
   so the key self-evicts after the reset.
3. **DB fallback** — Redis miss / Redis down → scan ``tarot_draws`` for
   the (owner, [week_start, week_end]) window. The architecture (§13)
   guarantees this remains correct, just slower (no sub-10ms budget).

This module is intentionally Protocol-driven on the Redis side so the
service has no hard dependency on ``redis.asyncio`` — tests run with
``redis=None`` (DB-only path) and the router-level dependency injection
hands in a real ``redis.asyncio.Redis`` in production. If the real
client raises ``redis.exceptions.RedisError`` (or any exception) the
service silently degrades to the DB path; we never propagate the
infrastructure failure to the caller.

PRD-Ref: FR-014 (weekly free quota), FR-016 (subscriber bypass).
Architecture-Ref: §6.4 (entitlement layering), §13 (Redis failure mode).
data_model-Ref: AP-33 (weekly free-quota count).
"""

from __future__ import annotations

import contextlib
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Literal, Protocol
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from voicesaju.db.models.tarot_draws import TarotDraw
from voicesaju.entitlement.service import EntitlementResult, check_entitlement

KST = ZoneInfo("Asia/Seoul")

# Sentinel returned in ``QuotaResult.remaining`` when the caller is a
# subscriber. Architecture spec uses the literal string "unlimited" in
# the paywall envelope; we keep an int constant so the type stays
# narrow inside the service and the router maps it to "unlimited" at
# the serialization edge.
UNLIMITED: int = -1

# Phase-1 quota: one free draw per ISO week. The PRD §FR-014 leaves
# the exact number tunable per growth experiment; we keep it as a
# module-level constant so the operator can flip it without churning
# the call sites.
WEEKLY_FREE_DRAWS: int = 1

# Redis TTL safety buffer (seconds). The architecture guarantees the
# counter is correct from the DB scan even if Redis evicts early, so
# the TTL is conservative + 1 day to soak up clock skew between app
# nodes.
_REDIS_TTL_BUFFER_SECONDS: int = 86_400  # 24h


# ---------------------------------------------------------------------------
# Public schema
# ---------------------------------------------------------------------------


@dataclass(slots=True, frozen=True)
class QuotaResult:
    """Structured response for :func:`check_weekly_free`.

    Fields:
        remaining: Draws left this ISO week. ``UNLIMITED`` for
            subscribers; otherwise a non-negative integer (typically 0
            or 1 with the Phase-1 weekly cap).
        is_unlimited: Convenience boolean — ``True`` iff
            ``remaining == UNLIMITED``. Router serializes this as
            ``"unlimited"`` in the JSON envelope.
        source: Diagnostic — which storage tier answered the call
            (``redis`` / ``db`` / ``subscription``). Useful for ops
            dashboards (NFR-016 ``tarot_seed_cache_hit_ratio`` peer
            metric ``tarot_quota_cache_hit_ratio``).
        iso_week_key: The Redis key suffix (``YYYY-Www``) the count
            applies to. Exposed so the router can log it consistently
            with other observability bits.
    """

    remaining: int
    is_unlimited: bool
    source: Literal["redis", "db", "subscription"]
    iso_week_key: str


# ---------------------------------------------------------------------------
# Redis Protocol — narrow contract.
# ---------------------------------------------------------------------------


class QuotaStore(Protocol):
    """Minimal Redis-compatible interface this module needs.

    Matches the shape of ``redis.asyncio.Redis`` for ``GET`` and
    ``SETEX`` so production wiring is a one-line ``redis=Redis(...)``.
    Tests pass :class:`InMemoryQuotaStore` (below) or a broken stub.
    """

    async def get(self, key: str) -> str | None: ...

    async def set(self, key: str, value: str, ex: int | None = None) -> None: ...


class InMemoryQuotaStore:
    """In-process Redis stub used only in tests.

    Why not just use ``unittest.mock.AsyncMock``? Because a typed stub
    is harder to misuse — it asserts the contract the service relies
    on and gives us a place to grow if we ever need to test eviction
    or TTL behaviour without standing up a real Redis.
    """

    def __init__(self) -> None:
        self._store: dict[str, str] = {}

    async def get(self, key: str) -> str | None:
        return self._store.get(key)

    async def set(self, key: str, value: str, ex: int | None = None) -> None:
        # We deliberately ignore ``ex`` — TTL behaviour is exercised by
        # the architecture, not by the unit test.
        del ex
        self._store[key] = value


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def iso_week_kst_key(d: date) -> str:
    """Return the ISO week key (``YYYY-Www``) for *d* in KST.

    Uses Python's stdlib ``date.isocalendar()`` which returns the
    canonical ISO 8601 year/week pair (handles the "January 1 lands in
    week 53 of the previous year" edge case correctly).
    """
    iso_year, iso_week, _ = d.isocalendar()
    return f"{iso_year:04d}-W{iso_week:02d}"


def _iso_week_bounds_kst(d: date) -> tuple[date, date]:
    """Return ``(monday, sunday)`` for the ISO week containing *d* in KST.

    Used by the DB-scan fallback to bound the ``tarot_draws.date_kst``
    range.
    """
    # weekday(): Mon=0, Sun=6. Subtract to get the Monday of the same week.
    monday = d - timedelta(days=d.weekday())
    sunday = monday + timedelta(days=6)
    return monday, sunday


def _to_kst_date(now: datetime) -> date:
    """Convert *now* to its KST calendar date.

    Accepts both naïve (assumed-KST) and tz-aware inputs. Tz-aware
    UTC instants are converted to KST before extracting the date so
    a request right before midnight UTC doesn't accidentally land in
    yesterday's KST week.
    """
    if now.tzinfo is None:
        return now.date()
    return now.astimezone(KST).date()


async def check_weekly_free(
    *,
    session: AsyncSession,
    user_id: str | None = None,
    device_id: str | None = None,
    now_kst: datetime | None = None,
    redis: QuotaStore | None = None,
    check_entitlement_fn: Callable[
        ..., Awaitable[EntitlementResult]
    ] = check_entitlement,
) -> QuotaResult:
    """Return the caller's remaining free draws this ISO week.

    Args:
        session: AsyncSession used for the DB-fallback scan + the
            subscription lookup (via ``check_entitlement_fn``).
        user_id: Resolved User.id for signed-in callers (architecture
            §6.4 ``vs_sess`` cookie path). Mutually exclusive with
            ``device_id`` at the *semantic* level — the caller is
            either authenticated or not — but the function tolerates
            both being passed (preferring ``user_id``) so the router
            can hand in whatever the auth middleware resolved.
        device_id: Resolved Device.id for non-member callers.
        now_kst: Override clock. Defaults to ``datetime.now(KST)``.
            Tests pass an explicit ``datetime(tzinfo=KST)`` to pin the
            ISO week deterministically.
        redis: Optional Redis-compatible store. Pass ``None`` to force
            the DB-scan path. If passed and a call raises, the failure
            is logged-as-tracing and the function silently degrades to
            the DB path (architecture §13).
        check_entitlement_fn: Override the entitlement service. The
            production default calls ``voicesaju.entitlement.service.
            check_entitlement``; tests inject lightweight stubs.

    Returns:
        :class:`QuotaResult` carrying ``remaining``, ``is_unlimited``,
        ``source``, and the ISO week key.

    Raises:
        ValueError: when neither ``user_id`` nor ``device_id`` is
            provided. The router converts this to a 400 / asserts at
            the auth boundary.
    """
    if not user_id and not device_id:
        raise ValueError(
            "check_weekly_free requires user_id or device_id; both are empty"
        )

    # Resolve owner id deterministically. user_id wins when both passed
    # so an authenticated subscriber still hits the subscription bypass
    # path even if the request also carries a (legacy) device cookie.
    subject_id = user_id or device_id
    assert subject_id is not None  # type narrowing for the rest of the fn

    now = now_kst or datetime.now(KST)
    today_kst = _to_kst_date(now)
    week_key = iso_week_kst_key(today_kst)

    # --- Stage 1: subscriber bypass ---------------------------------
    # Subscriptions only apply to authenticated users (devices can't
    # buy a subscription). Calling ``check_entitlement`` requires at
    # least one identifier; we pass whichever we have.
    if user_id:
        entitlement = await check_entitlement_fn(
            session=session,
            kind="tarot",
            user_id=user_id,
            device_id=device_id,
        )
        if entitlement.has_subscription_credit:
            return QuotaResult(
                remaining=UNLIMITED,
                is_unlimited=True,
                source="subscription",
                iso_week_key=week_key,
            )

    # --- Stage 2: Redis fast path -----------------------------------
    redis_key = _quota_redis_key(subject_id=subject_id, week_key=week_key)
    if redis is not None:
        try:
            cached = await redis.get(redis_key)
            if cached is not None:
                used = int(cached)
                return QuotaResult(
                    remaining=max(0, WEEKLY_FREE_DRAWS - used),
                    is_unlimited=False,
                    source="redis",
                    iso_week_key=week_key,
                )
        except Exception:
            # Redis is unavailable. Silently degrade to DB-scan; the
            # caller MUST still get a correct answer (architecture
            # §13 failure mode). The OTel tracer span will land in
            # ISSUE-049 — for now we don't even log to avoid pulling
            # in logging config here.
            pass

    # --- Stage 3: DB-scan fallback (AP-33) --------------------------
    used = await _db_scan_draws_this_week(
        session=session,
        user_id=user_id,
        device_id=device_id,
        today_kst=today_kst,
    )

    # Best-effort write-through cache so subsequent calls hit Redis.
    # Failure here is silent for the same reason as the read path.
    if redis is not None:
        ttl = _redis_ttl_for_week(today_kst)
        with contextlib.suppress(Exception):
            await redis.set(redis_key, str(used), ex=ttl)

    return QuotaResult(
        remaining=max(0, WEEKLY_FREE_DRAWS - used),
        is_unlimited=False,
        source="db",
        iso_week_key=week_key,
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _quota_redis_key(*, subject_id: str, week_key: str) -> str:
    """Return the canonical Redis key for the weekly quota counter."""
    return f"tarot:quota:{subject_id}:{week_key}"


def _redis_ttl_for_week(today_kst: date) -> int:
    """Seconds until Monday 00:00 KST next week + buffer.

    Setting the TTL to expire at the week boundary means the counter
    self-resets without our worker having to sweep it — one less
    operational concern.
    """
    _, sunday = _iso_week_bounds_kst(today_kst)
    next_monday = sunday + timedelta(days=1)
    midnight_next_monday_kst = datetime.combine(
        next_monday, datetime.min.time(), tzinfo=KST
    )
    now_kst = datetime.now(KST)
    seconds_until_reset = max(
        0, int((midnight_next_monday_kst - now_kst).total_seconds())
    )
    return seconds_until_reset + _REDIS_TTL_BUFFER_SECONDS


async def _db_scan_draws_this_week(
    *,
    session: AsyncSession,
    user_id: str | None,
    device_id: str | None,
    today_kst: date,
) -> int:
    """AP-33 fallback: count ``tarot_draws`` in the current ISO week.

    The query uses the compound index ``tarot_draws_user_date_desc_idx``
    (member path) which the data_model spec explicitly calls out as the
    weekly-quota fallback scanner. For the device path we rely on the
    smaller table scan — Phase-1 device counts are low enough that the
    cost is negligible.
    """
    monday, sunday = _iso_week_bounds_kst(today_kst)

    stmt = select(func.count(TarotDraw.id)).where(
        TarotDraw.date_kst >= monday,
        TarotDraw.date_kst <= sunday,
    )
    if user_id:
        stmt = stmt.where(TarotDraw.user_id == user_id)
    else:
        stmt = stmt.where(TarotDraw.device_id == device_id)

    result = await session.execute(stmt)
    return int(result.scalar_one() or 0)


__all__ = [
    "UNLIMITED",
    "WEEKLY_FREE_DRAWS",
    "InMemoryQuotaStore",
    "QuotaResult",
    "QuotaStore",
    "check_weekly_free",
    "iso_week_kst_key",
]
