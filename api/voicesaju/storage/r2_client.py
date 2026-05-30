"""R2Client façade over the storage adapter layer (ISSUE-038).

The audio finalize worker — and any future replay endpoint — consumes
this class rather than the raw adapter so that:

1. Key naming follows a single convention
   (``audio/readings/<reading_id>/...``).
2. ``STORAGE_PROVIDER`` is consulted at request time, not import time
   (matches the LLM/TTS/Payment factory pattern from ISSUE-099..102).
3. Tests can inject a custom :class:`StorageAdapter` via ``adapter=``
   without touching ``Settings``.

The Phase-2 swap from MockStorageAdapter → real R2 (boto3) is purely
internal: callers see the same :class:`R2Client` API.

PRD-Ref: FR-028 (audio replay), Architecture §8.4.
"""

from __future__ import annotations

from voicesaju.adapters import get_storage_adapter
from voicesaju.adapters.storage import StorageAdapter
from voicesaju.config import Settings

# Per the architecture §8.4 layout:
# ``audio/readings/<reading_id>/chunks/<seq>.mp3`` (per-sentence)
# ``audio/readings/<reading_id>/main.mp3`` (stitched)
DEFAULT_AUDIO_PREFIX: str = "audio/readings"


def audio_chunks_prefix(reading_id: str) -> str:
    """Key prefix for per-sentence chunks of *reading_id*."""
    return f"{DEFAULT_AUDIO_PREFIX}/{reading_id}/chunks"


def audio_main_key(reading_id: str) -> str:
    """Object key for the stitched main.mp3 of *reading_id*."""
    return f"{DEFAULT_AUDIO_PREFIX}/{reading_id}/main.mp3"


class R2Client:
    """Thin convenience wrapper around a :class:`StorageAdapter`.

    Construct one with ``R2Client.from_settings()`` to dispatch via
    ``STORAGE_PROVIDER``, or pass ``adapter=`` directly in tests.
    """

    def __init__(self, adapter: StorageAdapter) -> None:
        self._adapter = adapter

    @classmethod
    def from_settings(cls, settings: Settings | None = None) -> R2Client:
        """Factory: read ``STORAGE_PROVIDER`` and instantiate the adapter."""
        return cls(adapter=get_storage_adapter(settings=settings))

    # -- raw passthroughs ---------------------------------------------

    async def put_object(self, key: str, data: bytes) -> str:
        """Upload *data* at *key*, returning the canonical storage URL."""
        return await self._adapter.put_object(key, data)

    async def get_object(self, key: str) -> bytes:
        return await self._adapter.get_object(key)

    async def list_objects(self, prefix: str) -> list[str]:
        return await self._adapter.list_objects(prefix)

    async def delete_object(self, key: str) -> None:
        await self._adapter.delete_object(key)

    # -- audio-specific helpers ---------------------------------------

    async def list_chunks(self, reading_id: str) -> list[str]:
        """Return chunk keys for *reading_id* in upload order."""
        return await self._adapter.list_objects(audio_chunks_prefix(reading_id))

    async def put_chunk(self, reading_id: str, seq: int, data: bytes) -> str:
        """Upload a single per-sentence chunk; return its URL."""
        key = f"{audio_chunks_prefix(reading_id)}/{seq:04d}.mp3"
        return await self._adapter.put_object(key, data)

    async def put_main(self, reading_id: str, data: bytes) -> str:
        """Upload the stitched main.mp3; return its URL."""
        return await self._adapter.put_object(audio_main_key(reading_id), data)

    async def delete_chunks(self, reading_id: str) -> int:
        """Delete every chunk for *reading_id*; return the count removed."""
        keys = await self.list_chunks(reading_id)
        for key in keys:
            await self._adapter.delete_object(key)
        return len(keys)
