"""Toss WebView bridge token verification (ISSUE-046).

The Toss WebView hosts our app inside an in-app browser and signs an
HS256 JWT with our shared ``TOSS_BRIDGE_SECRET`` so we can identify the
user without going through the OAuth dance again. The token carries
``sub`` (the Toss user id) which we map onto our internal ``users``
table via ``toss_id``.

Architecture-Ref: §11.1 (vs_sess cookie + bridge), DEP-02 (bridge spec).
PRD-Ref: FR-016, FR-024, US-14.
"""

from __future__ import annotations

from dataclasses import dataclass

import jwt


class InvalidTossBridgeToken(Exception):
    """Raised when the bridge token fails any verification step."""


@dataclass(frozen=True, slots=True)
class TossBridgeIdentity:
    """Identity carried by a verified Toss bridge token.

    Just the Toss user id for now — the downstream ``UserService`` is
    responsible for linking this to / minting a row in ``users``.
    """

    toss_id: str


def verify_toss_bridge_token(
    *, token: str, secret: str, audience: str
) -> TossBridgeIdentity:
    """Verify ``token`` and return the carried identity.

    Raises :class:`InvalidTossBridgeToken` on any verification failure
    (bad signature, expired, missing/wrong audience, missing subject,
    malformed JWT, empty secret, ``alg=none`` downgrade attempt).
    """
    if not secret:
        # Deploy misconfiguration — refuse loudly so we never silently
        # accept tokens against an empty secret (which pyjwt rejects but
        # legacy callers may try to bypass via alg=none).
        raise RuntimeError("verify_toss_bridge_token: signing secret is empty")
    try:
        claims = jwt.decode(
            token,
            secret,
            algorithms=["HS256"],
            audience=audience,
            options={
                # Belt-and-braces — pyjwt already rejects alg=none with
                # an HS256 allow-list, but make it explicit.
                "require": ["exp", "sub"],
                "verify_signature": True,
                "verify_aud": True,
                "verify_exp": True,
            },
        )
    except jwt.PyJWTError as exc:
        raise InvalidTossBridgeToken(str(exc)) from exc

    sub = claims.get("sub")
    if not sub or not isinstance(sub, str):
        raise InvalidTossBridgeToken("missing or non-string sub claim")
    return TossBridgeIdentity(toss_id=sub)


__all__ = [
    "InvalidTossBridgeToken",
    "TossBridgeIdentity",
    "verify_toss_bridge_token",
]
