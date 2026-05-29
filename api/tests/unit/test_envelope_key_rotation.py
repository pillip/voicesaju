"""Key rotation must rewrap the DEK without touching the data payload (ISSUE-009).

After `rewrap_dek(envelope, new_kek_version)`:
- `wrapped_dek` and `kek_version` change
- `ciphertext`, `iv`, `tag`, `aad`, `algorithm` are unchanged
- Decryption still recovers the original plaintext
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


def test_rewrap_changes_only_wrapped_dek_and_version() -> None:
    user_id = uuid.uuid4()
    column = "birth_dt"
    original_plaintext = "2000-01-01T07:30:00Z"

    envelope = env_mod.encrypt_field(original_plaintext, user_id, column)
    original_version = envelope["kek_version"]

    new_version = "kek-2027-01"
    rewrapped = env_mod.rewrap_dek(envelope, new_version)

    # Changed:
    assert rewrapped["kek_version"] == new_version
    assert rewrapped["kek_version"] != original_version
    assert (
        rewrapped["wrapped_dek"] != envelope["wrapped_dek"]
    ), "wrapped_dek must change after rotation"

    # Unchanged (payload-side):
    for field in ("ciphertext", "iv", "tag", "aad", "algorithm"):
        assert (
            rewrapped[field] == envelope[field]
        ), f"{field} must NOT change during DEK rewrap"

    # Round-trip after rotation: plaintext recovers via the new wrapped DEK.
    # The LocalKMS instance is parameterised so a "new" version still resolves
    # against the same KEK in dev — that's fine for this assertion.
    recovered = env_mod.decrypt_field(rewrapped, user_id, column)
    assert recovered == original_plaintext


def test_rewrap_preserves_envelope_schema_keys() -> None:
    """Rewrapped envelope must still contain all 7 envelope keys."""
    user_id = uuid.uuid4()
    envelope = env_mod.encrypt_field("payload", user_id, "birth_dt")
    rewrapped = env_mod.rewrap_dek(envelope, "kek-2027-01")

    expected = {
        "kek_version",
        "wrapped_dek",
        "iv",
        "ciphertext",
        "tag",
        "algorithm",
        "aad",
    }
    assert expected.issubset(rewrapped.keys())
