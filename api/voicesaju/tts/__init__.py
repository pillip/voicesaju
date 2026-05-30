"""Streaming TTS client package (ISSUE-037).

This package houses the **structural** Supertone client + Korean-aware
sentence chunker that the reading pipeline (ISSUE-039) consumes.

Phase-1 wiring: the real Supertone API is gated behind ISSUE-036
provisioning. Until then, ``SupertoneAdapter`` (in
``voicesaju.adapters.tts``) delegates to ``MockTTSAdapter`` when
``TTS_PROVIDER=mock`` (the default) and only attempts the real HTTPX
path when ``TTS_PROVIDER=supertone`` + ``SUPERTONE_API_KEY`` is set.

PRD-Ref: NFR-002, FR-007, FR-034.
"""

from __future__ import annotations

from voicesaju.tts.chunker import (
    DEFAULT_MAX_SENTENCE_CHARS,
    chunk_sentences,
)
from voicesaju.tts.exceptions import (
    TTSFallthroughSignal,
    TTSFirstChunkTimeout,
    TTSMidStreamTimeout,
)
from voicesaju.tts.supertone_client import (
    DEFAULT_BACKOFF_BREACH_SECONDS,
    DEFAULT_CONCURRENCY,
    DEFAULT_FIRST_CHUNK_TIMEOUT_SECONDS,
    DEFAULT_MID_STREAM_TIMEOUT_SECONDS,
    AudioChunk,
    SupertoneClient,
    synthesize_stream,
)

__all__ = [
    "DEFAULT_BACKOFF_BREACH_SECONDS",
    "DEFAULT_CONCURRENCY",
    "DEFAULT_FIRST_CHUNK_TIMEOUT_SECONDS",
    "DEFAULT_MAX_SENTENCE_CHARS",
    "DEFAULT_MID_STREAM_TIMEOUT_SECONDS",
    "AudioChunk",
    "SupertoneClient",
    "TTSFallthroughSignal",
    "TTSFirstChunkTimeout",
    "TTSMidStreamTimeout",
    "chunk_sentences",
    "synthesize_stream",
]
