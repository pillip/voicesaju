"""Entitlement check service (ISSUE-040).

Computes whether a caller can start a paid action (a saju reading, for
now) given their available entitlements:

1. **Free token** (FR-003 nonmember_trial, FR-017 signup_grant,
   FR-023 failure_compensation, ops grants) — single-shot credits.
2. **Subscription credit** — `monthly_saju_remaining` quota on an
   active ``subscriptions`` row.
3. **No entitlement** — caller must purchase (frontend renders the
   paywall).

Architecture-Ref: §6.4 — entitlement lookup pattern.
data_model-Ref:

- **AP-16** "List active FreeTokens for User" (`user_id IS NOT NULL`).
- **AP-17** "Read FreeToken for Device (non-member trial)" (`device_id IS NOT NULL`).
- **AP-21** "Check active Subscription for User"
  (`status IN ('active','cancel_at_period_end','past_due')`).

Preferred consumption order is **token before subscription credit**
(architecture §6.4): we'd rather burn a one-shot credit than the
monthly quota, since granting another free token (e.g. as compensation)
is cheaper than refunding a subscription period.

The service does NOT mutate state — consumption is a separate concern
handled by :class:`voicesaju.services.token_service.TokenService` and
the reading pipeline that decrements
``Subscription.monthly_saju_remaining``.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from voicesaju.db.models.free_tokens import FreeToken
from voicesaju.db.models.subscriptions import Subscription

# Reading is the only ``kind`` exercised in M2; tarot and other paid
# resources will reuse this service in later milestones.
EntitlementKind = Literal["reading", "tarot"]

# Subscription statuses that grant entitlement. Architecture §6.4 +
# data_model AP-21: the partial unique index ``subscriptions_user_active_uq``
# includes all three — past_due is included because Toss may flag a
# transient billing failure that should NOT cut the user off mid-period.
_ACTIVE_SUB_STATUSES: frozenset[str] = frozenset(
    {"active", "cancel_at_period_end", "past_due"}
)


# ---------------------------------------------------------------------------
# Result schema
# ---------------------------------------------------------------------------


class EntitlementResult(BaseModel):
    """Structured response from :func:`check_entitlement`.

    Field semantics:

    - ``has_token``: caller has an unconsumed FreeToken (signup grant,
      nonmember trial, failure compensation, or ops grant).
    - ``token_id``: the FreeToken row id (if ``has_token=True``).
    - ``has_subscription_credit``: caller has an active subscription
      with ``monthly_saju_remaining > 0``.
    - ``subscription_id``: the Subscription row id (if the row exists,
      even when quota is 0 — useful for paywall messaging like "이번
      달 사주 풀이를 모두 사용했어요").
    - ``has_anything``: convenience boolean; true when either source can
      cover the action.
    - ``requires_payment``: convenience boolean; true when the caller
      cannot proceed without checking out.
    - ``preferred_kind``: which entitlement source the consumer should
      burn first (architecture §6.4 — free_token before subscription).

    The model is Pydantic so the value can be returned directly from a
    FastAPI handler without an additional serialisation layer.
    """

    has_token: bool = False
    token_id: str | None = None
    has_subscription_credit: bool = False
    subscription_id: str | None = None
    has_anything: bool = False
    requires_payment: bool = True
    preferred_kind: Literal["free_token", "subscription", "none"] = "none"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def check_entitlement(
    *,
    session: AsyncSession,
    kind: EntitlementKind = "reading",
    user_id: str | None = None,
    device_id: str | None = None,
) -> EntitlementResult:
    """Return the caller's entitlement summary.

    Exactly one of ``user_id`` and ``device_id`` should be provided —
    a signed-in caller is identified by ``user_id`` (architecture §6.1
    ``vs_sess`` cookie path), an anonymous caller by ``device_id``
    (FR-003 trial path).

    Passing both is accepted (signed-in users may still have a device
    row for analytics) — the lookup prefers ``user_id`` and falls back
    to ``device_id`` only for the FreeToken read.

    Raises ``ValueError`` when neither identifier is provided.

    Note on ``kind``: M2 only supports ``"reading"``; the field is kept
    on the API for forward compatibility with the daily-tarot quota
    (ISSUE-050+). Today's behaviour is identical for both values — the
    caller passes the kind so a future audit log can record what was
    being checked.
    """
    if not user_id and not device_id:
        raise ValueError(
            "check_entitlement requires user_id or device_id; both are empty"
        )

    # --- Free token lookup (AP-16 / AP-17) ---
    token_id = await _find_active_free_token(
        session=session, user_id=user_id, device_id=device_id
    )

    # --- Subscription lookup (AP-21) — signed-in users only ---
    sub_id, sub_has_credit = (None, False)
    if user_id:
        sub_id, sub_has_credit = await _find_active_subscription(
            session=session, user_id=user_id
        )

    has_token = token_id is not None
    has_anything = has_token or sub_has_credit
    requires_payment = not has_anything

    # Consumption preference: token first per architecture §6.4.
    preferred_kind: Literal["free_token", "subscription", "none"]
    if has_token:
        preferred_kind = "free_token"
    elif sub_has_credit:
        preferred_kind = "subscription"
    else:
        preferred_kind = "none"

    return EntitlementResult(
        has_token=has_token,
        token_id=token_id,
        has_subscription_credit=sub_has_credit,
        subscription_id=sub_id,
        has_anything=has_anything,
        requires_payment=requires_payment,
        preferred_kind=preferred_kind,
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


async def _find_active_free_token(
    *,
    session: AsyncSession,
    user_id: str | None,
    device_id: str | None,
) -> str | None:
    """Return the id of the first active FreeToken for the caller.

    Implements AP-16 (user_id path) and AP-17 (device_id fallback).
    Selection is stable for the same caller — we ``order_by(created_at)``
    so the oldest active token is consumed first (FIFO; matches
    intuition for "use my older grant before my newer one").
    """
    # Prefer user-owned tokens. We do NOT pick the device path for
    # signed-in users — device tokens were granted before sign-up and
    # may have been migrated to ``user_id`` by the FR-016 link path; if
    # they weren't, falling back here would shadow that bug.
    if user_id:
        stmt = (
            select(FreeToken.id)
            .where(
                FreeToken.user_id == user_id,
                FreeToken.consumed_at.is_(None),
            )
            .order_by(FreeToken.created_at.asc())
            .limit(1)
        )
        result = await session.execute(stmt)
        row = result.scalar_one_or_none()
        if row is not None:
            return str(row)
        return None

    # Anonymous path (FR-003): one ``nonmember_trial`` token per device.
    if device_id:
        stmt = (
            select(FreeToken.id)
            .where(
                FreeToken.device_id == device_id,
                FreeToken.consumed_at.is_(None),
                # AP-17 explicitly filters on ``kind='nonmember_trial'``
                # — other kinds are user-only (signup grant, comp, ops).
                FreeToken.kind == "nonmember_trial",
            )
            .order_by(FreeToken.created_at.asc())
            .limit(1)
        )
        result = await session.execute(stmt)
        row = result.scalar_one_or_none()
        if row is not None:
            return str(row)

    return None


async def _find_active_subscription(
    *,
    session: AsyncSession,
    user_id: str,
) -> tuple[str | None, bool]:
    """Return ``(subscription_id, has_credit)`` for ``user_id``.

    ``subscription_id`` is non-None whenever an active-status subscription
    row exists, regardless of remaining quota — this lets callers render
    "이번 달 사주 풀이를 모두 사용했어요" instead of the generic paywall
    when the user is a subscriber whose quota is exhausted.

    ``has_credit`` is True only when ``monthly_saju_remaining > 0``.
    """
    stmt = (
        select(Subscription.id, Subscription.monthly_saju_remaining).where(
            Subscription.user_id == user_id,
            Subscription.status.in_(_ACTIVE_SUB_STATUSES),
        )
        # Architecture §6.4 + data_model §4.14: one active sub per user
        # (partial unique index). ``limit(1)`` is defence in depth.
        .limit(1)
    )
    result = await session.execute(stmt)
    row = result.first()
    if row is None:
        return None, False
    sub_id, remaining = row
    return str(sub_id), int(remaining) > 0


__all__ = [
    "EntitlementKind",
    "EntitlementResult",
    "check_entitlement",
]
