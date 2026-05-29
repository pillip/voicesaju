"""IV / ciphertext randomness guard (ISSUE-009 AC: 100 distinct IVs).

The AC: 100 encryptions of the same plaintext yield 100 different IVs. This is
the cardinal property of AES-GCM — IV reuse with the same key would compromise
confidentiality entirely.
"""

from __future__ import annotations

import base64
import os
import uuid

import pytest

from voicesaju.security import envelope as env_mod


@pytest.fixture(autouse=True, scope="module")
def _local_kek_in_env() -> None:
    os.environ.setdefault(
        "LOCAL_KEK_BASE64", base64.b64encode(os.urandom(32)).decode("ascii")
    )
    os.environ.setdefault("KMS_PROVIDER", "local")


def test_iv_is_unique_across_100_encryptions() -> None:
    user_id = uuid.uuid4()
    plaintext = "2000-01-01T07:30:00Z"

    ivs: list[str] = []
    ciphertexts: list[str] = []
    for _ in range(100):
        env = env_mod.encrypt_field(plaintext, user_id, "birth_dt")
        ivs.append(env["iv"])
        ciphertexts.append(env["ciphertext"])

    assert (
        len(set(ivs)) == 100
    ), f"IVs must all be unique; got {100 - len(set(ivs))} collisions"
    # Ciphertexts derive from (IV, plaintext, key) — so they must also differ.
    assert (
        len(set(ciphertexts)) == 100
    ), "ciphertext must differ when IV differs (AES-GCM property)"


def test_iv_is_12_bytes() -> None:
    """data_model §4.25 mandates 12-byte (96-bit) IV — the GCM standard."""
    user_id = uuid.uuid4()
    env = env_mod.encrypt_field("x", user_id, "birth_dt")
    iv_bytes = base64.b64decode(env["iv"])
    assert len(iv_bytes) == 12, f"IV must be exactly 12 bytes, got {len(iv_bytes)}"


def test_tag_is_16_bytes() -> None:
    """data_model §4.25 mandates 16-byte (128-bit) GCM tag."""
    user_id = uuid.uuid4()
    env = env_mod.encrypt_field("x", user_id, "birth_dt")
    tag_bytes = base64.b64decode(env["tag"])
    assert len(tag_bytes) == 16, f"GCM tag must be 16 bytes, got {len(tag_bytes)}"


def test_dek_is_freshly_generated_per_call() -> None:
    """Per data_model §4.25: 'one DEK per row' — each encrypt yields a new DEK."""
    user_id = uuid.uuid4()
    a = env_mod.encrypt_field("x", user_id, "birth_dt")
    b = env_mod.encrypt_field("x", user_id, "birth_dt")
    assert (
        a["wrapped_dek"] != b["wrapped_dek"]
    ), "each encrypt must wrap a freshly-generated DEK"
