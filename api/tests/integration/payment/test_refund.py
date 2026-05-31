"""Integration tests for the automatic refund worker (ISSUE-076, FR-023).

Covers:

- AC1: a successful Toss refund flips ``payments.status`` to ``'refunded'``,
  inserts a ``refunds`` row with ``status='succeeded'`` and stamps
  ``finished_at``. ``payments.refunded_amount_krw`` is bumped to the
  full payment amount.
- AC2: when the upstream Toss refund call fails after all retries, the
  fallback path inserts a ``free_tokens`` row with
  ``kind='failure_compensation'`` owned by the paying user, sets
  ``refunds.status='failed_credited'`` and links
  ``refunds.fallback_token_id`` to the newly minted token. The payment
  row is left at its prior status (we did not actually refund money).
- AC3 (worker registry): ``refund_for_reading`` is registered in
  ``voicesaju.jobs.worker._JOB_REGISTRY`` so the in-memory queue can
  dispatch the job by name — matching the contract used by the audio
  finalize / og bake jobs (ISSUE-038, ISSUE-058).

All tests run against an in-memory SQLite engine + ``PAYMENT_PROVIDER=mock``
so they are deterministic, offline, and complete in well under the
60-second AC budget.
"""

from __future__ import annotations

import base64
from collections.abc import AsyncIterator
from datetime import UTC, datetime

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    async_sessionmaker,
    create_async_engine,
)

from voicesaju.db.base import Base
from voicesaju.db.models.free_tokens import FreeToken
from voicesaju.db.models.payments import Payment
from voicesaju.db.models.refunds import Refund
from voicesaju.db.models.users import User
from voicesaju.jobs.refund_retry import refund_for_reading
from voicesaju.jobs.worker import _JOB_REGISTRY
from voicesaju.payment.refund import (
    RefundResult,
    TossRefundError,
    refund_payment,
)


@pytest.fixture(autouse=True)
def _env_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
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


async def _seed_user(engine: AsyncEngine, kakao_sub: str = "refund-user-1") -> str:
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as s:
        u = User(kakao_sub=kakao_sub)
        s.add(u)
        await s.commit()
        await s.refresh(u)
        return str(u.id)


async def _seed_paid_payment(
    engine: AsyncEngine,
    *,
    user_id: str,
    amount_krw: int = 2900,
    reading_id: str | None = None,
) -> str:
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as s:
        p = Payment(
            user_id=user_id,
            kind="single",
            amount_krw=amount_krw,
            method="card",
            status="paid",
            toss_order_id=f"order-refund-{user_id[:8]}",
            toss_payment_key=f"key-refund-{user_id[:8]}",
            paid_at=datetime.now(tz=UTC),
        )
        s.add(p)
        await s.commit()
        await s.refresh(p)
        return str(p.id)


# ---------------------------------------------------------------------------
# AC1 — Toss refund succeeds → refunds.status='succeeded', payments.status='refunded'
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_refund_payment_success_flips_payment_and_inserts_refund(
    engine: AsyncEngine,
) -> None:
    """Happy path: Toss returns success → refund row marked succeeded."""
    user_id = await _seed_user(engine)
    payment_id = await _seed_paid_payment(engine, user_id=user_id, amount_krw=2900)

    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as session:
        # Inject a stub Toss client that returns success synchronously.
        async def _ok_refund(*, payment_key: str, amount_krw: int) -> str:
            assert payment_key == f"key-refund-{user_id[:8]}"
            assert amount_krw == 2900
            return "toss-refund-id-OK"

        result = await refund_payment(
            session=session,
            payment_id=payment_id,
            reason="llm_failure",
            toss_refund_call=_ok_refund,
        )
        await session.commit()

    assert isinstance(result, RefundResult)
    assert result.status == "succeeded"
    assert result.toss_refund_id == "toss-refund-id-OK"
    assert result.fallback_token_id is None

    # Verify payment + refund rows.
    async with maker() as session:
        pay = (
            await session.execute(select(Payment).where(Payment.id == payment_id))
        ).scalar_one()
        assert pay.status == "refunded"
        assert pay.refunded_amount_krw == 2900

        refund = (
            await session.execute(select(Refund).where(Refund.payment_id == payment_id))
        ).scalar_one()
        assert refund.status == "succeeded"
        assert refund.amount_krw == 2900
        assert refund.toss_refund_id == "toss-refund-id-OK"
        assert refund.finished_at is not None
        assert refund.reason == "llm_failure"
        assert refund.fallback_token_id is None

        # No fallback token should have been minted.
        tokens = (
            (
                await session.execute(
                    select(FreeToken).where(FreeToken.user_id == user_id)
                )
            )
            .scalars()
            .all()
        )
        assert tokens == []


# ---------------------------------------------------------------------------
# AC2 — Toss refund fails after retries → fallback FreeToken minted
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_refund_payment_toss_failure_credits_failure_compensation_token(
    engine: AsyncEngine,
) -> None:
    """Fallback path: Toss raises → free_tokens row with kind='failure_compensation'."""
    user_id = await _seed_user(engine)
    payment_id = await _seed_paid_payment(engine, user_id=user_id, amount_krw=2900)

    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as session:

        async def _failing_refund(*, payment_key: str, amount_krw: int) -> str:
            raise TossRefundError("Toss API unavailable")

        result = await refund_payment(
            session=session,
            payment_id=payment_id,
            reason="llm_failure",
            toss_refund_call=_failing_refund,
        )
        await session.commit()

    assert result.status == "failed_credited"
    assert result.toss_refund_id is None
    assert result.fallback_token_id is not None

    async with maker() as session:
        # Payment row stays paid — we did NOT actually refund money.
        pay = (
            await session.execute(select(Payment).where(Payment.id == payment_id))
        ).scalar_one()
        assert pay.status == "paid"
        assert pay.refunded_amount_krw == 0

        # Free token credited to the user.
        tokens = (
            (
                await session.execute(
                    select(FreeToken).where(FreeToken.user_id == user_id)
                )
            )
            .scalars()
            .all()
        )
        assert len(tokens) == 1
        assert tokens[0].kind == "failure_compensation"
        assert tokens[0].consumed_at is None

        # Refund row marked failed_credited and linked to the token.
        refund = (
            await session.execute(select(Refund).where(Refund.payment_id == payment_id))
        ).scalar_one()
        assert refund.status == "failed_credited"
        assert refund.fallback_token_id == str(tokens[0].id)
        assert refund.toss_refund_id is None
        assert refund.finished_at is not None


# ---------------------------------------------------------------------------
# AC3 — refund_for_reading registered + dispatchable end-to-end
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_refund_for_reading_is_registered_with_worker() -> None:
    """The worker registry must dispatch ``refund_for_reading`` by name."""
    assert "refund_for_reading" in _JOB_REGISTRY
    assert _JOB_REGISTRY["refund_for_reading"] is refund_for_reading


@pytest.mark.asyncio
async def test_refund_for_reading_resolves_reading_to_payment_and_refunds(
    engine: AsyncEngine,
) -> None:
    """``refund_for_reading(reading_id)`` finds the linked payment and refunds it."""
    from voicesaju.db.models.readings import Reading

    user_id = await _seed_user(engine)
    payment_id = await _seed_paid_payment(engine, user_id=user_id, amount_krw=2900)

    # Seed a reading row linked to the payment.
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as s:
        reading = Reading(
            user_id=user_id,
            category="love",
            character_key="sajununa",
            status="failed",
            entitlement_kind="payment",
            payment_id=payment_id,
        )
        s.add(reading)
        await s.commit()
        await s.refresh(reading)
        reading_id = str(reading.id)

    async def _ok_refund(*, payment_key: str, amount_krw: int) -> str:
        return "toss-from-reading-OK"

    result = await refund_for_reading(
        reading_id=reading_id,
        session_factory=lambda: maker(),
        toss_refund_call=_ok_refund,
    )
    assert result.status == "succeeded"
    assert result.payment_id == payment_id

    async with maker() as session:
        pay = (
            await session.execute(select(Payment).where(Payment.id == payment_id))
        ).scalar_one()
        assert pay.status == "refunded"
