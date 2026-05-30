"""Async job package (ISSUE-038).

The package houses the arq-compatible worker entry points + the job
implementations that the reading pipeline (ISSUE-039) enqueues.

Phase-1 wiring:
- ``worker.py`` exposes ``WorkerSettings`` (arq's expected attribute
  bag) but does NOT require a running Redis at import time. Tests
  use the in-memory ``InMemoryQueue`` stub to round-trip jobs.
- ``audio_finalize.py`` implements ``finalize_audio(reading_id)`` —
  the chunk-stitch + reading_audio update path called by the worker.

Phase-2 swap: real arq + Redis lands when the production deploy
process (ISSUE-074 / ISSUE-075) ships.

PRD-Ref: FR-028, Architecture §8.4.
"""

from __future__ import annotations

from voicesaju.jobs.audio_finalize import (
    AudioFinalizeResult,
    finalize_audio,
)
from voicesaju.jobs.worker import (
    InMemoryQueue,
    WorkerSettings,
    enqueue,
)

__all__ = [
    "AudioFinalizeResult",
    "InMemoryQueue",
    "WorkerSettings",
    "enqueue",
    "finalize_audio",
]
