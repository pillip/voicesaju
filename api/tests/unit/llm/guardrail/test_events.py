"""Unit tests for the ``record_violation`` helper (ISSUE-020).

Verifies the tone_violation_events row is persisted with sanitized
evidence, correct parent, layer="filter", and rejects misuse.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from voicesaju.db.base import Base
from voicesaju.db.models import (  # noqa: F401 - register metadata
    Device,
    FreeToken,
    Reading,
    TarotDraw,
    ToneViolationEvent,
    User,
)
from voicesaju.llm.guardrail.denylist import FilterResult, filter_chunk
from voicesaju.llm.guardrail.events import (
    ViolationParent,
    record_violation,
)


@pytest_asyncio.fixture
async def session() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as s:
        yield s
    await engine.dispose()


async def _make_reading_id(session: AsyncSession) -> str:
    """Insert a minimal Reading row and return its id.

    The ``readings_entitlement_chk`` CHECK requires exactly one
    entitlement source — we attach a free-token grant so the chain is
    well-formed.
    """
    user = User(id=str(uuid.uuid4()), kakao_sub=f"k-{uuid.uuid4()}")
    session.add(user)
    await session.flush()

    token = FreeToken(
        id=str(uuid.uuid4()),
        user_id=user.id,
        kind="signup_grant",
    )
    session.add(token)
    await session.flush()

    reading = Reading(
        id=str(uuid.uuid4()),
        user_id=user.id,
        category="general",
        status="pending",
        character_key="nuna",
        entitlement_kind="free_token",
        free_token_id=token.id,
    )
    session.add(reading)
    await session.flush()
    return reading.id


# ---------------------------------------------------------------------------
# happy path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_record_violation_inserts_row(session: AsyncSession) -> None:
    reading_id = await _make_reading_id(session)
    raw = "씨발 그 인간한테 돈 빌려주지 마세요."
    result = filter_chunk(raw)
    assert result.action in {"substitute", "block"}

    event = await record_violation(
        session,
        result=result,
        severity="severe",
        parent=ViolationParent(reading_id=reading_id),
        evidence_text=raw,
    )

    assert event.id is not None
    assert event.severity == "severe"
    assert event.layer == "filter"
    assert event.reading_id == reading_id
    assert event.tarot_id is None


@pytest.mark.asyncio
async def test_record_violation_masks_profanity_in_evidence(
    session: AsyncSession,
) -> None:
    """The verbatim profanity MUST NOT land in ``evidence_text``."""
    reading_id = await _make_reading_id(session)
    raw = "씨발 그 인간한테 돈 빌려주지 마세요."
    result = filter_chunk(raw)

    event = await record_violation(
        session,
        result=result,
        severity="severe",
        parent=ViolationParent(reading_id=reading_id),
        evidence_text=raw,
    )

    assert "씨발" not in event.evidence_text
    # Mask character is present.
    assert "●" in event.evidence_text


@pytest.mark.asyncio
async def test_record_violation_persists_to_table(
    session: AsyncSession,
) -> None:
    reading_id = await _make_reading_id(session)
    raw = "이 좆같은 운세는 그냥 무시하세요."
    result = filter_chunk(raw)

    await record_violation(
        session,
        result=result,
        severity="severe",
        parent=ViolationParent(reading_id=reading_id),
        evidence_text=raw,
    )

    rows = (await session.execute(select(ToneViolationEvent))).scalars().all()
    assert len(rows) == 1
    assert rows[0].reading_id == reading_id


# ---------------------------------------------------------------------------
# error paths
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_record_violation_rejects_pass_result(
    session: AsyncSession,
) -> None:
    reading_id = await _make_reading_id(session)
    pass_result = FilterResult(action="pass", text="clean")

    with pytest.raises(ValueError, match="passing FilterResult"):
        await record_violation(
            session,
            result=pass_result,
            severity="mild",
            parent=ViolationParent(reading_id=reading_id),
            evidence_text="clean",
        )


@pytest.mark.asyncio
async def test_record_violation_rejects_invalid_severity(
    session: AsyncSession,
) -> None:
    reading_id = await _make_reading_id(session)
    result = filter_chunk("씨발 운세")

    with pytest.raises(ValueError, match="invalid severity"):
        await record_violation(
            session,
            result=result,
            severity="critical",  # not in {mild, severe}
            parent=ViolationParent(reading_id=reading_id),
            evidence_text="씨발 운세",
        )


def test_violation_parent_requires_at_least_one_id() -> None:
    with pytest.raises(ValueError, match="reading_id / tarot_id"):
        ViolationParent()


def test_violation_parent_accepts_reading_id_alone() -> None:
    parent = ViolationParent(reading_id=str(uuid.uuid4()))
    assert parent.tarot_id is None


def test_violation_parent_accepts_tarot_id_alone() -> None:
    parent = ViolationParent(tarot_id=str(uuid.uuid4()))
    assert parent.reading_id is None
