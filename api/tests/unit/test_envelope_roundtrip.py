"""Round-trip encryption/decryption tests for security/envelope.py (ISSUE-009).

100 parametrized payloads of varying length must encrypt then decrypt back to
the original plaintext byte-for-byte. Also asserts the produced envelope shape
matches data_model §4.25 (all 7 keys present, AES-256-GCM algorithm).
"""

from __future__ import annotations

import os
import random
import string
import uuid

import pytest

# Module under test — imported lazily so pytest discovery doesn't fail at RED.
from voicesaju.security import envelope as env_mod

_ENVELOPE_KEYS = {
    "kek_version",
    "wrapped_dek",
    "iv",
    "ciphertext",
    "tag",
    "algorithm",
    "aad",
}


def _random_text(rng: random.Random, length: int) -> str:
    """Generate a random unicode-safe text of the given length."""
    alphabet = string.ascii_letters + string.digits + " 안녕하세요-한글_テスト+/="
    return "".join(rng.choices(alphabet, k=length))


@pytest.fixture(autouse=True, scope="module")
def _local_kek_in_env() -> None:
    """Ensure LOCAL_KEK_BASE64 is populated for LocalKMS during the test run."""
    import base64

    os.environ.setdefault(
        "LOCAL_KEK_BASE64", base64.b64encode(os.urandom(32)).decode("ascii")
    )
    os.environ.setdefault("KMS_PROVIDER", "local")


def _make_payloads() -> list[str]:
    rng = random.Random(20260528)  # deterministic test corpus
    # Lengths spread from 1..1000 so we exercise tiny and chunky inputs alike.
    lengths = [rng.randint(1, 1000) for _ in range(100)]
    return [_random_text(rng, n) for n in lengths]


@pytest.mark.parametrize("plaintext", _make_payloads())
def test_roundtrip_100_random_payloads(plaintext: str) -> None:
    user_id = uuid.uuid4()
    column = "birth_dt"

    envelope = env_mod.encrypt_field(plaintext, user_id, column)
    assert isinstance(envelope, dict), "envelope must be a dict (JSONB-shaped)"
    assert _ENVELOPE_KEYS.issubset(
        envelope.keys()
    ), f"envelope missing keys; got {sorted(envelope.keys())}"
    assert envelope["algorithm"] == "AES-256-GCM"
    assert envelope["aad"] == f"user_id:{user_id}:profile:{column}"

    recovered = env_mod.decrypt_field(envelope, user_id, column)
    assert recovered == plaintext, "decrypt_field must return the original plaintext"


def test_roundtrip_unicode_only() -> None:
    """Korean+emoji payload encrypts and decrypts byte-for-byte."""
    plaintext = "사주풀이 — 매운맛 🌶️ 2000-01-01T07:30:00+09:00"
    user_id = uuid.uuid4()

    envelope = env_mod.encrypt_field(plaintext, user_id, "birth_dt")
    recovered = env_mod.decrypt_field(envelope, user_id, "birth_dt")
    assert recovered == plaintext
