"""KMS provider abstraction for envelope encryption (ISSUE-009).

The `KMSProvider` Protocol defines the contract a KMS implementation must
satisfy. `LocalKMS` is a dev-only implementation that wraps DEKs with a
single KEK read from the `LOCAL_KEK_BASE64` environment variable.

Provider selection is controlled by `KMS_PROVIDER`:
- `local` (default) → `LocalKMS` reading `LOCAL_KEK_BASE64`.

Architecture: data_model §4.25 — one DEK per row, KEK held outside Postgres.
"""

from __future__ import annotations

import base64
import os
from typing import Any, Protocol, runtime_checkable

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

# 12-byte IV / 16-byte tag are the AES-GCM standard. We use AES-GCM (not AES-KW)
# for KEK→DEK wrapping too, with a dedicated wrap-IV stored in `wrapped_dek`.
_DEK_BYTES = 32  # AES-256
_WRAP_IV_BYTES = 12
DEFAULT_KEK_VERSION = "kek-2026-05"


class KMSError(RuntimeError):
    """Generic KMS failure (config missing, KEK invalid, etc.)."""


@runtime_checkable
class KMSProvider(Protocol):
    """Wraps and unwraps a per-row DEK using a Key Encryption Key (KEK)."""

    @property
    def kek_version(self) -> str: ...

    def wrap_dek(self, dek: bytes) -> dict[str, Any]:
        """Return JSON-serializable wrapping metadata for the given DEK."""
        ...

    def unwrap_dek(self, wrapped: dict[str, Any]) -> bytes:
        """Recover the DEK from its wrapping metadata."""
        ...


class LocalKMS:
    """Dev-only KMS that wraps DEKs with a single KEK from `LOCAL_KEK_BASE64`.

    Wrapping format (stored as a base64 JSON string in the envelope's
    `wrapped_dek` field):

        base64( wrap_iv (12 bytes) || AES-256-GCM( kek, dek ) )

    No AAD is bound to the wrap step — the envelope AAD already binds the
    encrypted payload to `user_id` + column.
    """

    def __init__(self, kek: bytes, version: str = DEFAULT_KEK_VERSION) -> None:
        if len(kek) != 32:
            raise KMSError(f"LocalKMS requires a 32-byte KEK (got {len(kek)} bytes)")
        self._kek = kek
        self._version = version

    @property
    def kek_version(self) -> str:
        return self._version

    @classmethod
    def from_env(cls, version: str = DEFAULT_KEK_VERSION) -> LocalKMS:
        raw = os.environ.get("LOCAL_KEK_BASE64")
        if not raw or raw == "REPLACE_WITH_BASE64_32_BYTES":
            raise KMSError(
                "LOCAL_KEK_BASE64 env var is missing or placeholder. "
                'Generate one with: python -c "import os,base64; '
                'print(base64.b64encode(os.urandom(32)).decode())"'
            )
        try:
            kek = base64.b64decode(raw, validate=True)
        except Exception as exc:  # noqa: BLE001 — re-raise as KMSError
            raise KMSError(f"LOCAL_KEK_BASE64 is not valid base64: {exc}") from exc
        return cls(kek=kek, version=version)

    def wrap_dek(self, dek: bytes) -> dict[str, Any]:
        if len(dek) != _DEK_BYTES:
            raise KMSError(f"DEK must be {_DEK_BYTES} bytes (got {len(dek)})")
        wrap_iv = os.urandom(_WRAP_IV_BYTES)
        wrapped = AESGCM(self._kek).encrypt(wrap_iv, dek, associated_data=None)
        blob = base64.b64encode(wrap_iv + wrapped).decode("ascii")
        return {"kek_version": self._version, "wrapped_dek": blob}

    def unwrap_dek(self, wrapped: dict[str, Any]) -> bytes:
        blob_b64 = wrapped.get("wrapped_dek")
        if not blob_b64:
            raise KMSError("missing wrapped_dek in envelope")
        try:
            blob = base64.b64decode(blob_b64, validate=True)
        except Exception as exc:  # noqa: BLE001
            raise KMSError(f"wrapped_dek is not valid base64: {exc}") from exc
        if len(blob) < _WRAP_IV_BYTES + 16:
            raise KMSError("wrapped_dek too short")
        wrap_iv, ct = blob[:_WRAP_IV_BYTES], blob[_WRAP_IV_BYTES:]
        return AESGCM(self._kek).decrypt(wrap_iv, ct, associated_data=None)


def get_kms_provider() -> KMSProvider:
    """Resolve the active KMS provider from environment.

    Currently only `local` is supported. Production KMS adapters (AWS KMS,
    GCP KMS) will plug in here behind the same Protocol.
    """
    name = os.environ.get("KMS_PROVIDER", "local").lower()
    if name == "local":
        return LocalKMS.from_env()
    raise KMSError(f"unknown KMS_PROVIDER: {name!r} (expected 'local')")
