"""Storage adapter Protocol + Phase-1 mock implementation (ISSUE-038).

Phase-1 ships ``MockStorageAdapter`` which persists to the local
filesystem under ``./.local_storage/`` (gitignored). This satisfies
the ISSUE-099 deferral note for ``MockStorageAdapter`` that ISSUE-005
(real R2) was supposed to be redirected through.

``R2StorageAdapter`` is the Phase-2 placeholder — it instantiates
without raising (so ``STORAGE_PROVIDER=r2`` can be set in env before
the real client lands) but raises ``NotImplementedError`` on first
business call so we surface the gap loudly instead of silently
losing audio.

PRD-Ref: FR-028 (audio replay), ISSUE-005 (deferred real R2),
ISSUE-099 (Mock adapter layer).
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Protocol, runtime_checkable

# Default local-fs root for ``MockStorageAdapter``. Lives in the repo
# root so devs can ``ls`` it during smoke runs; the ``.gitignore``
# entry keeps the artefacts out of commits.
DEFAULT_LOCAL_STORAGE_ROOT: Path = Path(".local_storage").resolve()


@runtime_checkable
class StorageAdapter(Protocol):
    """Provider-agnostic object-store client used by audio finalize.

    The Protocol is intentionally tiny — the audio pipeline only needs
    put / get / list / delete on byte blobs. Mirrors the boto3 S3
    object semantics so swapping :class:`R2StorageAdapter` in is a
    1:1 method-for-method replacement when ISSUE-005 lands.
    """

    async def put_object(self, key: str, data: bytes) -> str:
        """Upload *data* at *key*. Return the canonical storage URL."""
        ...

    async def get_object(self, key: str) -> bytes:
        """Read the blob at *key*. Raise ``KeyError`` if missing."""
        ...

    async def list_objects(self, prefix: str) -> list[str]:
        """List keys under *prefix* in lexicographic order."""
        ...

    async def delete_object(self, key: str) -> None:
        """Idempotent delete; no-op if the key does not exist."""
        ...


# ---------------------------------------------------------------------------
# MockStorageAdapter (Phase-1, local-fs)
# ---------------------------------------------------------------------------


class MockStorageAdapter:
    """Local-filesystem storage adapter (Phase-1 PoC).

    Persists blobs under ``root/<key>``. Tests inject a ``tmp_path``
    via ``root=`` so artefacts are isolated per-test. ``put_object``
    returns a ``file://`` URL so callers can round-trip via SignedURL-
    style code paths.

    Keys are sanitised: leading slashes are stripped and ``..`` is
    rejected so a stray ``../etc/passwd`` cannot escape the root.
    """

    def __init__(self, root: Path | str | None = None) -> None:
        self._root: Path = (
            Path(root) if root is not None else DEFAULT_LOCAL_STORAGE_ROOT
        )
        self._root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        """Resolve *key* to an absolute on-disk path inside the root.

        Raises:
            ValueError: if *key* attempts path traversal (``..``).
        """
        if ".." in Path(key).parts:
            raise ValueError(f"storage key contains path traversal: {key!r}")
        stripped = key.lstrip("/")
        return self._root / stripped

    async def put_object(self, key: str, data: bytes) -> str:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return path.as_uri()

    async def get_object(self, key: str) -> bytes:
        path = self._path(key)
        if not path.is_file():
            raise KeyError(key)
        return path.read_bytes()

    async def list_objects(self, prefix: str) -> list[str]:
        # Treat ``prefix`` as a key prefix — list every file under it
        # relative to the root, sorted lexicographically. We don't
        # honour the ``Delimiter='/'`` S3 quirk; the audio pipeline
        # uses bare prefixes (``audio/readings/<id>/chunks/``).
        base = self._path(prefix.rstrip("/"))
        if not base.exists():
            return []
        if base.is_file():
            return [prefix.rstrip("/")]
        return sorted(
            str(p.relative_to(self._root)) for p in base.rglob("*") if p.is_file()
        )

    async def delete_object(self, key: str) -> None:
        path = self._path(key)
        # Idempotent: ``missing_ok=True`` mirrors S3's "DELETE returns
        # 204 even when the key was already gone" behaviour.
        path.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# R2StorageAdapter (Phase-2 stub)
# ---------------------------------------------------------------------------


class R2StorageAdapter:
    """Phase-2 Cloudflare R2 adapter — instantiation succeeds, calls fail.

    Importing/instantiating does NOT raise so ``STORAGE_PROVIDER=r2``
    can be wired before the real boto3 client lands; first business
    call raises ``NotImplementedError`` pointing at ISSUE-005.
    """

    async def put_object(self, key: str, data: bytes) -> str:
        raise NotImplementedError(
            "R2StorageAdapter.put_object is a Phase-2 stub. "
            "See ISSUE-005 for real R2 provisioning."
        )

    async def get_object(self, key: str) -> bytes:
        raise NotImplementedError(
            "R2StorageAdapter.get_object is a Phase-2 stub. See ISSUE-005."
        )

    async def list_objects(self, prefix: str) -> list[str]:
        raise NotImplementedError(
            "R2StorageAdapter.list_objects is a Phase-2 stub. See ISSUE-005."
        )

    async def delete_object(self, key: str) -> None:
        raise NotImplementedError(
            "R2StorageAdapter.delete_object is a Phase-2 stub. See ISSUE-005."
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def content_sha256(data: bytes) -> str:
    """Stable content hash for ``reading_audio.content_hash``.

    Pulled here so the finalize worker + tests share one implementation.
    Returns the lowercase hex digest of the SHA-256.
    """
    return hashlib.sha256(data).hexdigest()


__all__ = [
    "DEFAULT_LOCAL_STORAGE_ROOT",
    "MockStorageAdapter",
    "R2StorageAdapter",
    "StorageAdapter",
    "content_sha256",
]
