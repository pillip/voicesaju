"""AES-256-GCM envelope encryption for per-row PII fields (ISSUE-009).

Envelope shape (data_model §4.25):

    {
      "kek_version":  "kek-2026-05",
      "wrapped_dek":  "BASE64(IV || AES-GCM(KEK, DEK))",
      "iv":           "BASE64(12-byte IV)",
      "ciphertext":   "BASE64(AES-256-GCM(DEK, plaintext))",
      "tag":          "BASE64(16-byte GCM tag)",
      "algorithm":    "AES-256-GCM",
      "aad":          "user_id:<uuid>:profile:<column>"
    }

Threat model notes (NFR-005):
- One DEK per row → single key compromise leaks only that row.
- AAD binds ciphertext to (`user_id`, column name) — defeats row-swap attacks.
- IV is 12 random bytes per encryption (never derived from plaintext).
- KEK never leaves the KMS provider; we store only the wrapped DEK in Postgres.
"""

from __future__ import annotations

import base64
import os
from typing import Any
from uuid import UUID

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from pydantic import BaseModel, Field

from voicesaju.security.kms import KMSError, KMSProvider, get_kms_provider

ALGORITHM = "AES-256-GCM"
_DEK_BYTES = 32  # AES-256 key length
_IV_BYTES = 12  # 96-bit IV — GCM standard
_TAG_BYTES = 16  # 128-bit tag — GCM standard


class AADMismatchError(ValueError):
    """Raised when an envelope is decrypted with the wrong AAD context.

    The underlying GCM tag verification fails (`InvalidTag`); we re-raise as
    this domain-level error so callers can distinguish "wrong user_id" from
    transport/serialization errors.
    """


class EnvelopeSchema(BaseModel):
    """Pydantic shape guard for the JSONB envelope (data_model §4.25)."""

    kek_version: str = Field(min_length=1)
    wrapped_dek: str = Field(min_length=1)
    iv: str = Field(min_length=1)
    ciphertext: str = Field(min_length=1)
    tag: str = Field(min_length=1)
    algorithm: str = Field(min_length=1)
    aad: str = Field(min_length=1)

    model_config = {"extra": "forbid"}


def _aad(user_id: UUID | str, column: str) -> bytes:
    return f"user_id:{user_id}:profile:{column}".encode()


def _b64e(raw: bytes) -> str:
    return base64.b64encode(raw).decode("ascii")


def _b64d(s: str) -> bytes:
    return base64.b64decode(s, validate=True)


def encrypt_field(
    plaintext: str,
    user_id: UUID | str,
    column: str,
    *,
    kms: KMSProvider | None = None,
) -> dict[str, Any]:
    """Encrypt `plaintext` and return a JSONB-shaped envelope dict.

    Args:
        plaintext: UTF-8 string to encrypt.
        user_id: PK of the owning user — bound into AAD.
        column: column name (e.g. `birth_dt`) — bound into AAD.
        kms: optional KMSProvider; defaults to env-configured provider.

    Returns:
        Dict with the 7 canonical envelope keys. All binary fields are
        base64-encoded for JSONB storage.
    """
    if kms is None:
        kms = get_kms_provider()

    dek = os.urandom(_DEK_BYTES)
    iv = os.urandom(_IV_BYTES)
    aad = _aad(user_id, column)

    sealed = AESGCM(dek).encrypt(iv, plaintext.encode("utf-8"), aad)
    # `cryptography`'s AESGCM produces ciphertext||tag concatenated.
    # data_model §4.25 stores them separately — split them out.
    ciphertext, tag = sealed[:-_TAG_BYTES], sealed[-_TAG_BYTES:]

    wrap = kms.wrap_dek(dek)
    envelope: dict[str, Any] = {
        "kek_version": wrap["kek_version"],
        "wrapped_dek": wrap["wrapped_dek"],
        "iv": _b64e(iv),
        "ciphertext": _b64e(ciphertext),
        "tag": _b64e(tag),
        "algorithm": ALGORITHM,
        "aad": aad.decode("utf-8"),
    }
    # Best-effort shape validation (no I/O cost).
    EnvelopeSchema.model_validate(envelope)
    return envelope


def decrypt_field(
    envelope: dict[str, Any],
    user_id: UUID | str,
    column: str,
    *,
    kms: KMSProvider | None = None,
) -> str:
    """Decrypt an envelope and return the original plaintext string.

    Raises:
        AADMismatchError: if AAD or GCM tag verification fails (wrong user,
            wrong column, tampered ciphertext, or wrong KEK).
        KMSError: if the wrapped DEK cannot be unwrapped.
        ValueError: if the envelope schema is invalid.
    """
    EnvelopeSchema.model_validate(envelope)

    if envelope["algorithm"] != ALGORITHM:
        raise ValueError(
            f"unsupported algorithm: {envelope['algorithm']!r} (expected {ALGORITHM!r})"
        )

    expected_aad = _aad(user_id, column).decode("utf-8")
    if envelope["aad"] != expected_aad:
        raise AADMismatchError(
            "envelope AAD does not match (user_id, column) — refusing to decrypt"
        )

    if kms is None:
        kms = get_kms_provider()

    try:
        dek = kms.unwrap_dek(envelope)
    except InvalidTag as exc:
        raise AADMismatchError("DEK unwrap failed (KEK mismatch)") from exc

    iv = _b64d(envelope["iv"])
    ciphertext = _b64d(envelope["ciphertext"])
    tag = _b64d(envelope["tag"])
    aad = expected_aad.encode("utf-8")

    try:
        plaintext_bytes = AESGCM(dek).decrypt(iv, ciphertext + tag, aad)
    except InvalidTag as exc:
        raise AADMismatchError(
            "AES-GCM tag verification failed — ciphertext or AAD mismatch"
        ) from exc

    return plaintext_bytes.decode("utf-8")


def rewrap_dek(
    envelope: dict[str, Any],
    new_kek_version: str,
    *,
    old_kms: KMSProvider | None = None,
    new_kms: KMSProvider | None = None,
) -> dict[str, Any]:
    """Rewrap the DEK under a new KEK version without re-encrypting the payload.

    Per data_model §4.25 the rotation strategy is "kek_version bump + re-wrap
    of DEK, no plaintext rotation". The returned envelope keeps `ciphertext`,
    `iv`, `tag`, `aad`, `algorithm` byte-for-byte identical to the input — only
    `wrapped_dek` and `kek_version` change.

    Args:
        envelope: the existing envelope to rotate.
        new_kek_version: version label to embed in the rewrapped envelope.
        old_kms: provider that wrapped the DEK originally. Defaults to the
            currently-configured provider.
        new_kms: provider that will wrap with the new KEK. Defaults to the
            currently-configured provider. For LocalKMS in dev both default to
            the same instance — the version label differs to satisfy the
            rotation contract.
    """
    EnvelopeSchema.model_validate(envelope)

    if old_kms is None:
        old_kms = get_kms_provider()
    if new_kms is None:
        new_kms = get_kms_provider()

    try:
        dek = old_kms.unwrap_dek(envelope)
    except InvalidTag as exc:
        raise KMSError("DEK unwrap failed during rotation") from exc

    new_wrap = new_kms.wrap_dek(dek)

    rewrapped = dict(envelope)
    rewrapped["wrapped_dek"] = new_wrap["wrapped_dek"]
    rewrapped["kek_version"] = new_kek_version

    EnvelopeSchema.model_validate(rewrapped)
    return rewrapped
