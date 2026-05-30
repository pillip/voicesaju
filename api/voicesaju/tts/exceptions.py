"""TTS-domain exceptions surfaced by the Supertone client (ISSUE-037).

These map onto the FR-034 fallback table in `docs/architecture.md` §8.3:

- ``TTSFirstChunkTimeout`` → row "First TTS chunk > 5s".
  Pipeline reaction: switch the reading to text-only mode.
- ``TTSMidStreamTimeout`` → row "Mid-stream TTS chunk failure".
  Pipeline reaction: skip audio for that sentence, continue the rest.
- ``TTSFallthroughSignal`` → row "Rate-limit (429) breach > 8s".
  Pipeline reaction: switch the reading to text-only mode.

The exceptions are intentionally narrow — the client raises them at the
*observation* point (timeout fires, rate-limit window breached). Higher
layers translate them into SSE events.
"""

from __future__ import annotations


class TTSError(RuntimeError):
    """Base class for every TTS exception raised by the Supertone client.

    Catching this gives the pipeline a single ``except`` clause for
    "anything TTS-related" without having to enumerate the subclasses
    while still letting handlers branch on the concrete type.
    """


class TTSFirstChunkTimeout(TTSError):
    """Raised when the first audio chunk does not arrive within the budget.

    PRD-Ref: NFR-002, FR-034 ("First TTS chunk > 5s" row).
    Default budget: ``DEFAULT_FIRST_CHUNK_TIMEOUT_SECONDS`` (5.0s) in
    :mod:`voicesaju.tts.supertone_client`.
    """


class TTSMidStreamTimeout(TTSError):
    """Raised when a single mid-stream sentence exceeds the per-chunk budget.

    PRD-Ref: FR-034 ("Mid-stream TTS chunk failure" row).
    Default budget: ``DEFAULT_MID_STREAM_TIMEOUT_SECONDS`` (3.0s).
    """


class TTSFallthroughSignal(TTSError):
    """Raised when rate-limit (HTTP 429) backoff exceeds the breach budget.

    PRD-Ref: FR-034 ("Rate-limit (429) from Supertone" row).
    Default budget: ``DEFAULT_BACKOFF_BREACH_SECONDS`` (8.0s of cumulative
    breach). The pipeline catches this and degrades the reading to
    text-only mode (banner: 음성 서비스가 일시적으로 불가합니다…).
    """


__all__ = [
    "TTSError",
    "TTSFallthroughSignal",
    "TTSFirstChunkTimeout",
    "TTSMidStreamTimeout",
]
