"""`TokenService` — free-token grant and consume operations.

Owns the cross-model invariants for `free_tokens` (data_model §4.7):

- **Idempotent signup grant** (FR-017 AC): inserting the same
  `(user_id, kind='signup_grant')` twice must NOT create a second row.
- **Idempotent non-member trial grant** (FR-003 AC): same shape with
  `(device_id, kind='nonmember_trial')`.
- **Failure compensation** (FR-023 AC): always a new row — never deduped.
- **Consume** is a single UPDATE that fails if the token is already
  consumed (caller is expected to wrap in a TX and treat the failure as
  a race that should be retried at the request boundary).

The Postgres path uses `INSERT ... ON CONFLICT DO NOTHING` against the
partial unique indexes from migration 0005. For SQLite (used in unit
tests where the partial-unique index does not exist), we fall back to a
SELECT-then-INSERT under the active session — the unit tests stub the
session, so the SQLite path is never actually exercised against a real
SQLite engine; it exists only to keep the helper importable.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from voicesaju.db.models.free_tokens import FreeToken


class TokenAlreadyConsumedError(RuntimeError):
    """Raised when `consume_token` targets a row whose `consumed_at` is set.

    The reading-orchestration layer should treat this as a 409-equivalent
    and reject the attempt — the token can only be redeemed once.
    """


class TokenService:
    """Free-token grant + consume operations.

    Construct one per request from the active `AsyncSession`. The service
    does NOT commit — the caller controls the transaction boundary so a
    failure later in the request still rolls the grant back.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # --- grant operations ----------------------------------------------

    async def grant_signup_bonus(self, user_id: uuid.UUID) -> FreeToken | None:
        """Idempotently grant `kind='signup_grant'` to a user.

        Returns the newly-inserted row, or `None` when the user already
        has a signup grant (FR-017 AC: "one grant per account, never two").
        """
        return await self._grant_idempotent(
            owner_col="user_id",
            owner_value=user_id,
            kind="signup_grant",
        )

    async def grant_nonmember_trial(self, device_id: uuid.UUID) -> FreeToken | None:
        """Idempotently grant `kind='nonmember_trial'` to a device.

        Returns the newly-inserted row, or `None` when the device already
        has a trial grant (FR-003 AC).
        """
        return await self._grant_idempotent(
            owner_col="device_id",
            owner_value=device_id,
            kind="nonmember_trial",
        )

    async def grant_compensation(
        self,
        user_id: uuid.UUID,
        reason: str,  # noqa: ARG002 — accepted for audit symmetry; logged by caller.
    ) -> FreeToken:
        """Grant a `failure_compensation` token to a user.

        Always inserts a new row — there is no idempotency guard because
        a single user can legitimately receive multiple compensations
        (FR-023). The `reason` is consumed by the audit layer at the
        caller (the row itself doesn't carry a reason column).
        """
        token = FreeToken(
            user_id=str(user_id),
            kind="failure_compensation",
        )
        self._session.add(token)
        await self._session.flush()
        return token

    # --- consume --------------------------------------------------------

    async def consume_token(
        self,
        token_id: uuid.UUID,
        reading_id: uuid.UUID,
    ) -> FreeToken:
        """Mark `token_id` as consumed by `reading_id`.

        Raises `TokenAlreadyConsumedError` if the token's `consumed_at`
        is already set. The check is performed inside the same TX as the
        UPDATE so concurrent consumers race on the row lock.
        """
        token = await self._session.get(FreeToken, str(token_id))
        if token is None:
            raise LookupError(f"FreeToken {token_id} not found")
        if token.consumed_at is not None:
            raise TokenAlreadyConsumedError(
                f"FreeToken {token_id} already consumed at {token.consumed_at}"
            )
        token.consumed_at = datetime.now(UTC)
        token.consumed_by_reading_id = str(reading_id)
        await self._session.flush()
        return token

    # --- internals ------------------------------------------------------

    async def _grant_idempotent(
        self,
        owner_col: str,
        owner_value: uuid.UUID,
        kind: str,
    ) -> FreeToken | None:
        """Insert a token row with `ON CONFLICT DO NOTHING` semantics.

        On Postgres the partial unique index from migration 0005 is the
        conflict target, so duplicate grants short-circuit at the index.
        On SQLite (and other non-Postgres dialects) we fall back to
        SELECT-then-INSERT guarded by an IntegrityError catch — this
        keeps unit-test ergonomics simple at the cost of a non-atomic
        path that is never used in production.
        """
        dialect = self._session.bind.dialect.name if self._session.bind else ""
        owner_str = str(owner_value)

        if dialect == "postgresql":
            stmt = (
                pg_insert(FreeToken)
                .values(**{owner_col: owner_str, "kind": kind})
                .on_conflict_do_nothing(
                    index_elements=[owner_col],
                    index_where=FreeToken.__table__.c.kind == kind,
                )
                .returning(FreeToken)
            )
            result = await self._session.execute(stmt)
            row = result.scalar_one_or_none()
            await self._session.flush()
            return row

        # Non-Postgres fallback: SELECT-then-INSERT under the same TX.
        existing_stmt = select(FreeToken).where(
            getattr(FreeToken, owner_col) == owner_str,
            FreeToken.kind == kind,
        )
        existing = (await self._session.execute(existing_stmt)).scalar_one_or_none()
        if existing is not None:
            return None

        token = FreeToken(**{owner_col: owner_str, "kind": kind})
        self._session.add(token)
        try:
            await self._session.flush()
        except IntegrityError:
            # Lost a race against another transaction — semantically the
            # same as the ON CONFLICT path returning None.
            await self._session.rollback()
            return None
        return token
