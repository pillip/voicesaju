"""GDPR/PIPA hard-delete cron worker (ISSUE-088, NFR-005).

Daily job that finds users whose ``users.deleted_at`` is older than
``HARD_DELETE_GRACE_DAYS`` (30 days per data_model.md §11) and removes
them — along with every dependent row across the data model.

Cascade strategy:

- ``users.deleted_at`` is the soft-delete marker (ISSUE-072). The
  user has had 30 days to log back in and restore their data
  (architecture §11.1).
- We use a SQL ``DELETE FROM users WHERE id = :user_id`` and let the
  database FK ``ON DELETE CASCADE`` chain do the actual row removal
  across the 11 dependent tables (profiles, saju_charts, readings,
  reading_audio, reading_followups, reading_transcripts,
  tone_violation_events, tarot_draws, payments, refunds,
  subscriptions, quote_cards, free_tokens). The cascades are
  declared in the ORM models (data_model §4.* per-table).
- Before deleting the user row we collect every R2 audio key owned
  by their readings (``reading_audio.r2_key``, plus chunks via
  ``R2Client.audio_chunks_prefix``) and issue a delete against the
  storage adapter. The DB-side cascade does NOT touch R2 — only
  rows.
- Every successful hard-delete writes one ``audit_events`` row with
  ``event_type='hard_delete'`` + payload listing the R2 keys
  removed + the dependent row counts (architecture AP-08, NFR-005
  audit trail).

Why we don't manually walk the cascade:
   The schema's ``ON DELETE CASCADE`` is already the contract — re-
   implementing the walk in Python would create a divergence risk
   between the migration and the cron worker. We DO query for R2 keys
   ahead of time (since the DB delete will wipe them) but the
   row-level cascade is delegated.

PRD-Ref: NFR-005. Architecture-Ref: §11, AP-08, AP-54.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from voicesaju.db.models.audit_events import AuditEvent
from voicesaju.db.models.reading_audio import ReadingAudio
from voicesaju.db.models.readings import Reading
from voicesaju.db.models.users import User
from voicesaju.jobs.worker import register
from voicesaju.storage.r2_client import R2Client, audio_chunks_prefix

logger = logging.getLogger(__name__)

#: 30-day grace window per data_model.md §11. Lifted out as a module
#: constant so tests can monkey-patch it down to milliseconds without
#: touching the cron schedule.
HARD_DELETE_GRACE_DAYS: int = 30


async def _collect_r2_keys(
    session: AsyncSession,
    user_id: str,
    *,
    r2: R2Client,
) -> list[str]:
    """Return every R2 object key owned (transitively) by *user_id*.

    Looks up every ``reading_audio`` row whose ``readings.user_id``
    matches, then expands per-reading into:

    1. The stitched ``reading_audio.r2_key`` (one per reading).
    2. The per-sentence chunks under ``audio_chunks_prefix(reading_id)``
       — listed against the storage adapter so the cron picks up keys
       written by ``finalize_audio`` (ISSUE-038) even if the
       ``reading_audio`` row lost its ``r2_key`` link.

    Keys are de-duplicated before return. Missing prefixes (e.g.
    readings where TTS never completed) contribute an empty list.
    """
    # SELECT reading_audio.r2_key, readings.id
    # WHERE readings.user_id = :uid
    rows = (
        await session.execute(
            select(ReadingAudio.r2_key, Reading.id)
            .join(Reading, ReadingAudio.reading_id == Reading.id)
            .where(Reading.user_id == user_id)
        )
    ).all()

    keys: list[str] = []
    seen: set[str] = set()

    for r2_key, reading_id in rows:
        if r2_key and r2_key not in seen:
            keys.append(r2_key)
            seen.add(r2_key)
        # Pull per-sentence chunks via the prefix listing. R2Client's
        # list_objects is hermetic against the in-memory adapter for
        # tests and against the real R2 client in production.
        try:
            chunk_keys = await r2.list_objects(audio_chunks_prefix(str(reading_id)))
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning(
                "hard_delete: list_chunks failed for reading_id=%s: %s",
                reading_id,
                exc,
            )
            chunk_keys = []
        for ck in chunk_keys:
            if ck not in seen:
                keys.append(ck)
                seen.add(ck)

    return keys


async def _delete_r2_objects(r2: R2Client, keys: list[str]) -> int:
    """Delete every key. Errors per-key are logged + skipped.

    We intentionally do NOT raise on individual delete failures — a
    half-deleted user is worse than retrying next-day, because the
    DB rows are already gone. The job logs each failure for ops
    triage and returns the count actually removed.
    """
    deleted = 0
    for key in keys:
        try:
            await r2.delete_object(key)
            deleted += 1
        except Exception as exc:
            logger.warning("hard_delete: r2 delete_object(%s) failed: %s", key, exc)
    return deleted


async def _write_audit_event(
    session: AsyncSession,
    *,
    user_id: str,
    r2_keys_removed: list[str],
) -> None:
    """Append one ``audit_events`` row for the user being hard-deleted.

    The row is the only persistent trace that the user existed once
    the cascade fires — by design, per the data_model §11 retention
    policy. ``payload`` captures the R2 keys removed so a future
    forensic query can confirm storage hygiene.
    """
    event = AuditEvent(
        entity_type="user",
        entity_id=user_id,
        event_type="hard_delete",
        payload={
            "r2_keys_removed": r2_keys_removed,
            "r2_key_count": len(r2_keys_removed),
            "removed_at": datetime.now(UTC).isoformat(),
        },
    )
    session.add(event)


async def _find_due_users(
    session: AsyncSession,
    *,
    now: datetime,
    grace_days: int,
) -> list[str]:
    """Return user IDs whose ``deleted_at`` is older than the grace window.

    Returns IDs only (not ORM rows) so the caller can issue per-user
    DELETEs without keeping the original rows in the session — that
    avoids the autoflush surprise where SQLAlchemy tries to re-write
    them between operations.
    """
    cutoff = now - timedelta(days=grace_days)
    rows = (
        await session.execute(
            select(User.id).where(
                User.deleted_at.is_not(None),
                User.deleted_at < cutoff,
            )
        )
    ).all()
    return [str(r[0]) for r in rows]


async def _hard_delete_one(
    session: AsyncSession,
    user_id: str,
    *,
    r2: R2Client,
) -> dict[str, Any]:
    """Remove one user + cascade dependents + clean R2 + emit audit.

    Returns a dict suitable for the worker's per-iteration log.

    Operation order is intentional:

    1. Collect R2 keys (we need the readings table intact).
    2. Write the audit_events row (still needs the user PK to be a
       valid string but does NOT FK to it).
    3. Issue the user DELETE — the DB cascade fires synchronously.
    4. Commit the transaction. The audit row is now durable and the
       user is gone.
    5. Best-effort R2 cleanup. The audit row already records the
       keys we *intended* to delete — partial R2 cleanup is a
       known-good fallback per the architecture §11.4 note that R2
       lifecycle policies independently sweep orphaned keys after 90
       days.
    """
    r2_keys = await _collect_r2_keys(session, user_id, r2=r2)
    await _write_audit_event(session, user_id=user_id, r2_keys_removed=r2_keys)

    # The cascade chain handles all dependent rows. ``rowcount`` is
    # the number of *user* rows removed — always 0 or 1 for a single-
    # id delete; we surface it for logging.
    result = await session.execute(delete(User).where(User.id == user_id))
    deleted_rows = int(result.rowcount or 0)

    await session.commit()

    r2_deleted = await _delete_r2_objects(r2, r2_keys)

    return {
        "user_id": user_id,
        "user_rows_deleted": deleted_rows,
        "r2_keys_collected": len(r2_keys),
        "r2_keys_deleted": r2_deleted,
    }


@register
async def hard_delete_expired_users(
    *args: Any,
    session_factory: Callable[[], Awaitable[AsyncSession]] | None = None,
    r2: R2Client | None = None,
    now: datetime | None = None,
    grace_days: int = HARD_DELETE_GRACE_DAYS,
    **kwargs: Any,
) -> dict[str, Any]:
    """arq-discoverable cron entrypoint (ISSUE-088, NFR-005).

    Daily schedule: iterate every ``users`` row whose ``deleted_at``
    is older than the 30-day grace window and hard-delete it.

    Dependency injection:

    - ``session_factory`` — async callable returning an
      ``AsyncSession``. Defaults to opening one via
      :func:`voicesaju.db.engine.get_session` (the same path the API
      uses). Tests inject a fixture-backed factory.
    - ``r2`` — :class:`R2Client`. Defaults to
      :meth:`R2Client.from_settings` so the storage provider env var
      is honored. Tests inject the in-memory adapter.
    - ``now`` — wall-clock anchor. Defaults to ``datetime.now(UTC)``.
      Tests inject a fixed instant so the cutoff math is deterministic.
    - ``grace_days`` — override the 30-day window. Tests inject 0 so
      ``deleted_at = now()`` is immediately due.

    Returns a summary dict with ``users_processed`` and per-user
    results so the arq job log carries enough detail for a postmortem.

    AC mapping:
       1. Users soft-deleted 31+ days ago are removed with all
          dependents (DB cascade).
       2. One audit_events row per user with ``event_type='hard_delete'``.
       3. R2 keys for the user's readings are removed.
    """
    anchor = now or datetime.now(UTC)
    r2_client = r2 or R2Client.from_settings()

    if session_factory is None:
        # Default: borrow a session via the engine helper. The helper
        # is an async generator; we wrap it so the caller can stay
        # in a tidy ``async with`` shape.
        from voicesaju.db.engine import get_session

        async def _default_factory() -> AsyncSession:
            # ``get_session`` is a FastAPI dependency that yields one
            # session per iteration; for a worker we want a fresh
            # session per user, so we iterate the generator manually.
            gen = get_session()
            return await gen.__anext__()  # type: ignore[union-attr]

        session_factory = _default_factory  # type: ignore[assignment]

    results: list[dict[str, Any]] = []
    # First pass: find every due id with a short-lived session.
    assert session_factory is not None  # for mypy
    discover_session = await session_factory()
    try:
        due_ids = await _find_due_users(
            discover_session, now=anchor, grace_days=grace_days
        )
    finally:
        await discover_session.close()

    logger.info(
        "hard_delete_expired_users: %d users due (grace_days=%d, cutoff=%s)",
        len(due_ids),
        grace_days,
        (anchor - timedelta(days=grace_days)).isoformat(),
    )

    # Per-user pass — fresh session each so a failure on one doesn't
    # leak partial state into the next.
    for uid in due_ids:
        session = await session_factory()
        try:
            summary = await _hard_delete_one(session, uid, r2=r2_client)
            results.append(summary)
            logger.info(
                "hard_delete_expired_users: user_id=%s removed (r2=%d/%d)",
                summary["user_id"],
                summary["r2_keys_deleted"],
                summary["r2_keys_collected"],
            )
        except Exception:  # noqa: BLE001 - we want to keep going
            logger.exception("hard_delete_expired_users: failed for user_id=%s", uid)
            results.append({"user_id": uid, "error": True})
        finally:
            await session.close()

    return {
        "users_processed": len(results),
        "results": results,
    }


__all__ = [
    "HARD_DELETE_GRACE_DAYS",
    "hard_delete_expired_users",
]
