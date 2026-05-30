"""Unit tests for the Toss webhook signature helper (ISSUE-045).

Covers:

- HMAC-SHA256 over the raw request body.
- ``hmac.compare_digest`` constant-time comparison.
- Case-insensitive hex digest (Toss sometimes returns upper-hex).
- Empty / wrong-length signatures are rejected without raising.
"""

from __future__ import annotations

import hashlib
import hmac

import pytest

from voicesaju.payment.webhook_signature import (
    build_signature,
    verify_signature,
)


def _sign(body: bytes, secret: str) -> str:
    return hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


def test_build_signature_returns_hex_digest() -> None:
    """build_signature() is HMAC-SHA256 hex over the body."""
    body = b'{"eventType":"PAYMENT_DONE"}'
    sig = build_signature(body, "my-secret")
    assert sig == _sign(body, "my-secret")
    assert len(sig) == 64  # 32 bytes hex


def test_verify_signature_accepts_matching_hex() -> None:
    body = b'{"foo":"bar"}'
    sig = _sign(body, "shared-secret")
    assert verify_signature(body=body, signature=sig, secret="shared-secret") is True


def test_verify_signature_rejects_wrong_secret() -> None:
    body = b'{"foo":"bar"}'
    sig = _sign(body, "shared-secret")
    assert verify_signature(body=body, signature=sig, secret="other-secret") is False


def test_verify_signature_rejects_tampered_body() -> None:
    body = b'{"foo":"bar"}'
    sig = _sign(body, "shared-secret")
    tampered = b'{"foo":"BAR"}'
    assert (
        verify_signature(body=tampered, signature=sig, secret="shared-secret") is False
    )


def test_verify_signature_accepts_upper_hex_digest() -> None:
    """Toss occasionally returns the hex digest in uppercase — accept both."""
    body = b'{"event":"x"}'
    sig = _sign(body, "secret").upper()
    assert verify_signature(body=body, signature=sig, secret="secret") is True


@pytest.mark.parametrize("bad_sig", ["", "not-hex", "abcd", "z" * 64])
def test_verify_signature_rejects_malformed(bad_sig: str) -> None:
    """Empty, wrong-length, and non-hex strings return False (no exception)."""
    body = b'{"foo":"bar"}'
    assert verify_signature(body=body, signature=bad_sig, secret="secret") is False


def test_verify_signature_rejects_empty_secret() -> None:
    """An empty secret must NOT validate — defence against misconfiguration."""
    body = b'{"foo":"bar"}'
    sig = _sign(body, "")
    # Even when the HMAC numerically matches, our helper rejects empty secrets
    # so a half-configured deploy can't accept arbitrary webhooks.
    assert verify_signature(body=body, signature=sig, secret="") is False
