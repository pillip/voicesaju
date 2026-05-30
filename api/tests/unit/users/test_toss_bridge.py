"""Unit tests for the Toss bridge token verification service (ISSUE-046).

Token shape (HS256 JWT signed with ``TOSS_BRIDGE_SECRET``):

```
{
  "iss": "tosspayments",
  "aud": "voicesaju",
  "sub": "<toss_id>",          # Toss-side stable user id
  "exp": <unix ts>,
  "iat": <unix ts>,
}
```

Tests exercise:

- Valid token → returns a ``TossBridgeIdentity`` carrying the ``toss_id``.
- Bad signature → raises ``InvalidTossBridgeToken``.
- Expired → raises ``InvalidTossBridgeToken``.
- Wrong audience → raises ``InvalidTossBridgeToken``.
- Missing ``sub`` claim → raises ``InvalidTossBridgeToken``.
- Empty secret → raises ``RuntimeError`` (defence-in-depth: refuses to
  verify without a configured secret).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import jwt
import pytest

from voicesaju.users.services.toss_bridge_service import (
    InvalidTossBridgeToken,
    TossBridgeIdentity,
    verify_toss_bridge_token,
)

SECRET = "test-toss-bridge-secret-do-not-use-in-prod"
AUDIENCE = "voicesaju"


def _make_token(
    *,
    sub: str | None = "toss-user-123",
    aud: str | None = AUDIENCE,
    secret: str = SECRET,
    exp_delta_seconds: int = 300,
    iss: str = "tosspayments",
    extra: dict | None = None,
) -> str:
    now = datetime.now(tz=UTC)
    claims: dict = {
        "iss": iss,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=exp_delta_seconds)).timestamp()),
    }
    if sub is not None:
        claims["sub"] = sub
    if aud is not None:
        claims["aud"] = aud
    if extra:
        claims.update(extra)
    return jwt.encode(claims, secret, algorithm="HS256")


def test_verify_valid_token_returns_identity() -> None:
    token = _make_token()
    identity = verify_toss_bridge_token(token=token, secret=SECRET, audience=AUDIENCE)
    assert isinstance(identity, TossBridgeIdentity)
    assert identity.toss_id == "toss-user-123"


def test_verify_rejects_bad_signature() -> None:
    token = _make_token(secret="other-secret")
    with pytest.raises(InvalidTossBridgeToken):
        verify_toss_bridge_token(token=token, secret=SECRET, audience=AUDIENCE)


def test_verify_rejects_expired_token() -> None:
    token = _make_token(exp_delta_seconds=-60)  # 60s in the past
    with pytest.raises(InvalidTossBridgeToken):
        verify_toss_bridge_token(token=token, secret=SECRET, audience=AUDIENCE)


def test_verify_rejects_wrong_audience() -> None:
    token = _make_token(aud="some-other-app")
    with pytest.raises(InvalidTossBridgeToken):
        verify_toss_bridge_token(token=token, secret=SECRET, audience=AUDIENCE)


def test_verify_rejects_missing_sub() -> None:
    token = _make_token(sub=None)
    with pytest.raises(InvalidTossBridgeToken):
        verify_toss_bridge_token(token=token, secret=SECRET, audience=AUDIENCE)


def test_verify_rejects_empty_secret() -> None:
    token = _make_token()
    # A half-configured deploy must refuse loudly rather than fall back
    # to a silent decode (jwt.decode with key="" succeeds for "none" alg).
    with pytest.raises(RuntimeError):
        verify_toss_bridge_token(token=token, secret="", audience=AUDIENCE)


def test_verify_rejects_malformed_token() -> None:
    with pytest.raises(InvalidTossBridgeToken):
        verify_toss_bridge_token(token="not-a-jwt", secret=SECRET, audience=AUDIENCE)


def test_verify_rejects_none_alg_token() -> None:
    """A token with ``alg: none`` must never validate, even without a key.

    Defence against the classic JWT-library "accept alg: none" bug —
    pyjwt 2+ disallows this by default, but we assert it explicitly so a
    future library swap or misconfiguration is caught by the test suite.
    """
    # Manually construct an ``alg: none`` token (pyjwt won't sign one for
    # us). The decode side should raise InvalidTossBridgeToken.
    import base64
    import json

    header = base64.urlsafe_b64encode(
        json.dumps({"alg": "none", "typ": "JWT"}).encode()
    ).rstrip(b"=")
    payload = base64.urlsafe_b64encode(
        json.dumps(
            {
                "iss": "tosspayments",
                "aud": AUDIENCE,
                "sub": "evil",
                "exp": int((datetime.now(tz=UTC) + timedelta(hours=1)).timestamp()),
            }
        ).encode()
    ).rstrip(b"=")
    bogus_token = f"{header.decode()}.{payload.decode()}."

    with pytest.raises(InvalidTossBridgeToken):
        verify_toss_bridge_token(token=bogus_token, secret=SECRET, audience=AUDIENCE)
