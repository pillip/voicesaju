"""AAD-mismatch must abort decryption (ISSUE-009 AC: cross-user decrypt fails).

Decrypting an envelope encrypted for user_A with user_B's id MUST raise. The
test asserts a custom `AADMismatchError` (or InvalidTag from `cryptography`),
not a silent corrupt-plaintext fall-through.
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


def test_decrypt_with_other_user_raises() -> None:
    user_a = uuid.uuid4()
    user_b = uuid.uuid4()
    envelope = env_mod.encrypt_field("2000-01-01T07:30:00Z", user_a, "birth_dt")

    # The implementation may raise AADMismatchError (preferred) or InvalidTag —
    # both indicate authentication failure. We accept either to match the
    # AC's "decryption fails" intent without over-specifying.
    with pytest.raises(env_mod.AADMismatchError) as excinfo:
        env_mod.decrypt_field(envelope, user_b, "birth_dt")

    # Whatever it raises, it must NOT silently succeed — the *test* of that
    # is `pytest.raises` itself. Defensive assertion: it should at least be
    # an exception, not a plain truthy return.
    assert excinfo.value is not None


def test_decrypt_with_other_column_raises() -> None:
    """Same user, wrong column name in AAD — must also fail authentication."""
    user_id = uuid.uuid4()
    envelope = env_mod.encrypt_field("payload", user_id, "birth_dt")
    with pytest.raises(env_mod.AADMismatchError):
        env_mod.decrypt_field(envelope, user_id, "phone_e164")


def test_decrypt_with_tampered_ciphertext_raises() -> None:
    """Bit-flip the ciphertext — GCM tag check must reject."""
    user_id = uuid.uuid4()
    envelope = env_mod.encrypt_field("payload", user_id, "birth_dt")

    # Flip one byte in the base64 ciphertext (decode → tamper → re-encode).
    raw = base64.b64decode(envelope["ciphertext"])
    tampered = bytes([raw[0] ^ 0x01]) + raw[1:]
    envelope["ciphertext"] = base64.b64encode(tampered).decode("ascii")

    with pytest.raises(env_mod.AADMismatchError):
        env_mod.decrypt_field(envelope, user_id, "birth_dt")
