"""Object-store façade package (ISSUE-038).

The package exposes :class:`R2Client` — a thin façade that selects the
right :class:`~voicesaju.adapters.storage.StorageAdapter` from
``settings.storage_provider`` and presents the read/write/list/delete
contract expected by the audio finalize worker.

Phase-1 routes through :class:`MockStorageAdapter` (local-fs); Phase-2
swaps to :class:`R2StorageAdapter` (boto3 against Cloudflare R2) once
ISSUE-005 ships.

PRD-Ref: FR-028.
"""

from __future__ import annotations

from voicesaju.storage.r2_client import (
    DEFAULT_AUDIO_PREFIX,
    R2Client,
    audio_chunks_prefix,
    audio_main_key,
)

__all__ = [
    "DEFAULT_AUDIO_PREFIX",
    "R2Client",
    "audio_chunks_prefix",
    "audio_main_key",
]
