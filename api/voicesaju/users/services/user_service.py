"""`UserService` — find-or-create-by-provider for OAuth callbacks.

PRD-Ref: FR-016 (account identity), FR-017 (signup grant idempotency),
architecture §11 (dup-detection by `email_hash`).

Identity-resolution order (architecture §11.1):

1. Look up by the provider's subject id (`kakao_sub` or `apple_sub`).
   If found → existing user; no grant.
2. Otherwise, if `email_hash` is provided, look up by `email_hash`.
   If found → link the new provider id to that user; no grant
   (this is the "two providers, same human" case in architecture §11
   that prevents accidental account splits).
3. Otherwise → insert a new user row. The caller is expected to call
   ``TokenService.grant_signup_bonus(user.id)`` after a successful
   commit; the partial-unique index keeps that grant idempotent across
   retries.

The service does NOT commit — the route controls the TX boundary.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from voicesaju.db.models.users import User

# Marker returned alongside the User so the route knows whether to mint
# the signup grant. We use a literal-string sentinel rather than a bool
# so the audit log path can distinguish "linked existing user via
# email_hash" (no grant) from "found by provider sub" (no grant) and
# "new user" (grant).
FindOrCreateOutcome = Literal["found_by_sub", "linked_by_email", "created"]

Provider = Literal["kakao", "apple"]


@dataclass
class UserResolution:
    """Result of `find_or_create_by_provider` carrying the outcome flag."""

    user: User
    outcome: FindOrCreateOutcome


def hash_email(email: str | None) -> str | None:
    """Return a deterministic sha256 hex digest of `email.lower()`.

    Returns None when the provider didn't yield an email (Apple's
    `email=None` after first-time auth, for example). Lowercasing
    prevents the same Gmail address arriving via Kakao (`Foo@gmail`)
    and Apple (`foo@gmail`) from splitting the account.
    """
    if not email:
        return None
    return hashlib.sha256(email.strip().lower().encode("utf-8")).hexdigest()


class UserService:
    """find-or-create-by-provider for OAuth callbacks (FR-016)."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def find_or_create_by_provider(
        self,
        *,
        provider: Provider,
        subject_id: str,
        email: str | None,
    ) -> UserResolution:
        """Resolve a User row from a provider callback.

        See module docstring for the exact resolution order.
        """
        sub_col = User.kakao_sub if provider == "kakao" else User.apple_sub
        email_hash = hash_email(email)

        # Step 1 — direct lookup by provider sub.
        stmt = select(User).where(sub_col == subject_id)
        existing = (await self._session.execute(stmt)).scalar_one_or_none()
        if existing is not None:
            # Refresh email_hash if it was previously null (rare: the
            # first sign-in from this provider didn't carry an email).
            if existing.email_hash is None and email_hash is not None:
                existing.email_hash = email_hash
                await self._session.flush()
            return UserResolution(user=existing, outcome="found_by_sub")

        # Step 2 — link by email_hash (architecture §11 dup-detection).
        if email_hash is not None:
            link_stmt = select(User).where(User.email_hash == email_hash)
            link_existing = (
                await self._session.execute(link_stmt)
            ).scalar_one_or_none()
            if link_existing is not None:
                # Attach the new provider id to the existing account.
                if provider == "kakao":
                    link_existing.kakao_sub = subject_id
                else:
                    link_existing.apple_sub = subject_id
                await self._session.flush()
                return UserResolution(user=link_existing, outcome="linked_by_email")

        # Step 3 — fresh insert.
        new_user = User(
            kakao_sub=subject_id if provider == "kakao" else None,
            apple_sub=subject_id if provider == "apple" else None,
            email_hash=email_hash,
        )
        self._session.add(new_user)
        await self._session.flush()
        return UserResolution(user=new_user, outcome="created")


__all__ = [
    "FindOrCreateOutcome",
    "Provider",
    "UserResolution",
    "UserService",
    "hash_email",
]
