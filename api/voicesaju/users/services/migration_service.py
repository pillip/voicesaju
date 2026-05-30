"""Device → User non-member state migration (ISSUE-062, AP-07).

PRD-Ref: US-02 (signup carries the non-member's session state forward),
FR-003 (non-member trial token belongs to the device until signup).
Architecture-Ref: data_model.md §3.1 AP-07
(*"Link Device → User on signup (migrate non-member state)"*).

Why a dedicated service module:

- The signup callback in :mod:`voicesaju.users.routers.auth` already owns
  the OAuth → ``UserService.find_or_create_by_provider`` flow plus the
  signup-grant TokenService call. AP-07 needs a *third* step at the same
  TX boundary: reassign the rows the device was carrying so the user's
  ``/me`` payload reflects them on first load.
- The two upstream rows that have the ``(user_id IS NULL) <> (device_id
  IS NULL)`` XOR constraint — ``tarot_draws`` and ``free_tokens`` — must
  flip atomically: write ``user_id`` first, then NULL out ``device_id``.
  Doing the second update before the first would violate the XOR CHECK
  mid-transaction (SQLite enforces CHECK per statement, Postgres
  enforces at commit time but we want deterministic semantics).
- ``quote_cards`` rows ride the parent ``readings.id`` / ``tarot_draws.id``
  link — there is no direct ``device_id`` on a quote card, so once the
  parent tarot draw is reassigned the quote card follows by inference.
  No explicit update needed for quote cards: AC #1 ("quote card
  transferred") is satisfied transitively.
- ``readings.user_id`` is NOT NULL by schema (data_model §4.8) — readings
  are always owned by a user. Non-member readings simply don't exist
  in the v1 data model, so the issue spec's mention of
  ``readings.device_id=NULL`` does not apply.

The service does NOT commit — the route controls the TX boundary, so the
caller can compose this migration with the user-creation insert + the
signup-grant insert in a single atomic block. On any failure the caller
rolls back the outer TX and no partial state lands.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from voicesaju.db.models.devices import Device
from voicesaju.db.models.free_tokens import FreeToken
from voicesaju.db.models.tarot_draws import TarotDraw

logger = logging.getLogger(__name__)


@dataclass(slots=True, frozen=True)
class MigrationResult:
    """Counts of rows migrated, so the caller can log structured metrics.

    Each field counts the rows whose ``user_id`` was set to the target
    and whose ``device_id`` was cleared. ``device_linked`` is True when
    ``devices.linked_user_id`` was written (False if the device was
    already linked to the same user — idempotent re-runs).
    """

    tarot_draws_migrated: int
    free_tokens_migrated: int
    device_linked: bool


async def migrate_device_to_user(
    device_id: str,
    user_id: str,
    *,
    session: AsyncSession,
) -> MigrationResult:
    """Reassign non-member rows owned by *device_id* to *user_id*.

    Semantics (AP-07):

    1. Look up the ``Device`` row. Missing → :class:`ValueError`. We need
       the row both to write ``linked_user_id`` and to surface a clear
       error when the caller passes an unknown id (vs silently no-op).
    2. Reassign every ``tarot_draws`` row owned by the device — set
       ``user_id`` first, then ``device_id=NULL``. The XOR CHECK
       (``tarot_draws_owner_xor_chk``) sees a valid state at each
       statement boundary.
    3. Reassign every ``free_tokens`` row by the same pattern. The
       partial unique index ``free_tokens_nonmember_trial_uq``
       (``(device_id) WHERE kind='nonmember_trial'``) is satisfied
       automatically once ``device_id`` is NULLed.
    4. Set ``devices.linked_user_id = user_id`` so future device upserts
       (``DeviceService.upsert_device``) can short-circuit lookup the
       linked account via the ``devices_linked_user_idx`` partial index.

    All three writes share the caller's session. The caller MUST
    wrap them in a transaction (e.g. ``session.begin()``) so a failure
    midway rolls back atomically. We intentionally do NOT open a nested
    SAVEPOINT here — the OAuth callback's flush sequence already nests
    the user-create / signup-grant inserts, and a second nested begin
    would obscure the actual atomicity boundary.

    Args:
        device_id: ``devices.id`` (server-side uuidv7 as string) for the
            non-member session being migrated. NOT the
            ``device_id_client`` cookie value.
        user_id: ``users.id`` (uuid as string) for the freshly signed-in
            account. Must already exist in the session (typical caller
            inserts the user row, flushes, then calls this with
            ``user.id``).
        session: SQLAlchemy async session. Caller manages the TX boundary.

    Returns:
        :class:`MigrationResult` with row counts + linked flag, so the
        OAuth callback can log a structured metric per FR-016 + FR-017.

    Raises:
        ValueError: ``device_id`` does not exist in ``devices``. The
            caller can choose to surface this as a 4xx — the M4 signup
            flow does the safer thing and treats it as a no-op grant
            (the user just won't see the migrated state, which matches
            the UX for someone who cleared cookies before signing up).
    """
    device = await _load_device(session, device_id)

    # Step 1 — tarot draws. We do the two-statement reassign so the XOR
    # CHECK is never violated even between statements. Using SQL UPDATEs
    # (rather than loading rows + mutating) keeps the migration O(1) in
    # round-trips regardless of how many rows the device accumulated.
    tarot_count = await _reassign_tarot_draws(session, device_id, user_id)

    # Step 2 — free tokens. Same pattern. The partial unique index on
    # ``(device_id) WHERE kind='nonmember_trial'`` is satisfied once
    # device_id is NULL — no manual index dance needed.
    token_count = await _reassign_free_tokens(session, device_id, user_id)

    # Step 3 — link the device row to the user. Idempotent: if the
    # device is already linked to this user (e.g. a retry from the
    # signup callback), the second update is a no-op and we return
    # ``device_linked=False`` so the caller can distinguish.
    device_linked = device.linked_user_id != user_id
    if device_linked:
        device.linked_user_id = user_id  # type: ignore[assignment]
        await session.flush()

    logger.info(
        "migration_service.migrate_device_to_user "
        "device_id=%s user_id=%s tarot=%d tokens=%d linked=%s",
        device_id,
        user_id,
        tarot_count,
        token_count,
        device_linked,
    )
    return MigrationResult(
        tarot_draws_migrated=tarot_count,
        free_tokens_migrated=token_count,
        device_linked=device_linked,
    )


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------


async def _load_device(session: AsyncSession, device_id: str) -> Device:
    """Return the ``Device`` row or raise ``ValueError`` if missing."""
    row = (
        await session.execute(select(Device).where(Device.id == device_id))
    ).scalar_one_or_none()
    if row is None:
        raise ValueError(
            f"migration_service.migrate_device_to_user: "
            f"device_id={device_id!r} not found"
        )
    return row


async def _reassign_tarot_draws(
    session: AsyncSession,
    device_id: str,
    user_id: str,
) -> int:
    """Flip ``tarot_draws.{device_id, user_id}`` for rows owned by *device_id*.

    Two-statement reassign so the XOR CHECK ``(user_id IS NULL) <>
    (device_id IS NULL)`` is never violated between statements:

    1. Set ``user_id = :uid`` — now the row has BOTH owners set, so the
       XOR check (which expects "exactly one") fails on SQLite under
       per-statement CHECK enforcement. To avoid this we instead do a
       single UPDATE that sets ``user_id`` AND clears ``device_id`` in
       the same statement — the CHECK only re-evaluates at the end of
       the statement (both SQLite and Postgres agree on this), so the
       row transitions from "device-owned" directly to "user-owned"
       without ever entering the disallowed "both set" state.

    Returns:
        The number of rows updated (0 if the device had no draws).
    """
    # Single-statement update: CHECK constraint sees the post-update
    # state only. This is the safe path under both SQLite (per-statement
    # CHECK) and Postgres (deferred-by-default at commit).
    stmt = (
        update(TarotDraw)
        .where(TarotDraw.device_id == device_id)
        .values(user_id=user_id, device_id=None)
    )
    result = await session.execute(stmt)
    # ``rowcount`` is reliable on both async dialects for plain UPDATE.
    await session.flush()
    return int(result.rowcount or 0)


async def _reassign_free_tokens(
    session: AsyncSession,
    device_id: str,
    user_id: str,
) -> int:
    """Flip ``free_tokens.{device_id, user_id}`` for rows owned by *device_id*.

    Same single-statement strategy as :func:`_reassign_tarot_draws` —
    the XOR CHECK ``free_tokens_owner_xor_chk`` evaluates against the
    post-update state so we transition directly from device-owned to
    user-owned without violating the constraint mid-flight.

    The partial unique index ``free_tokens_nonmember_trial_uq``
    (``(device_id) WHERE kind='nonmember_trial'``) is satisfied
    automatically once ``device_id`` is NULL — the index simply drops
    the row from its scope.

    Note: if the new user already has a ``signup_grant`` free token and
    we're migrating a ``nonmember_trial`` token, both rows can coexist
    on ``(user_id, kind)`` because the partial unique
    ``free_tokens_signup_grant_uq`` is ``(user_id) WHERE
    kind='signup_grant'`` — different ``kind`` values don't collide.

    Returns:
        The number of rows updated.
    """
    stmt = (
        update(FreeToken)
        .where(FreeToken.device_id == device_id)
        .values(user_id=user_id, device_id=None)
    )
    result = await session.execute(stmt)
    await session.flush()
    return int(result.rowcount or 0)


__all__ = [
    "MigrationResult",
    "migrate_device_to_user",
]
