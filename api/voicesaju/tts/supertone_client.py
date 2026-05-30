"""Structural Supertone streaming client (ISSUE-037, Phase-1 wiring).

This module provides the **shape** of the eventual real-Supertone
adapter so the reading pipeline (ISSUE-039) can be implemented and
tested today:

- ``synthesize_stream(text_stream, voice_id)`` async-yields
  :class:`AudioChunk` objects in sentence order.
- ``SupertoneClient`` owns the underlying :class:`httpx.AsyncClient`
  lifetime, the concurrency cap, and the 429-backoff timer.

**Phase-1 vs Phase-2**:

- Tests exercise the structure with :mod:`respx` against an in-process
  ``httpx`` transport. No real Supertone HTTP is ever attempted in CI.
- The real production path requires ``SUPERTONE_API_KEY`` to be set —
  ``SupertoneClient`` raises a clear ``RuntimeError`` at request time
  (not import time) if the env is missing under
  ``TTS_PROVIDER=supertone``. The real provisioning lives behind
  ISSUE-036.

PRD-Ref: NFR-002 (first-chunk ≤ 1.5s), FR-007 (streaming TTS),
FR-034 (text-only fallback).
"""

from __future__ import annotations

import asyncio
import os
import random
import time
from collections.abc import AsyncIterable, AsyncIterator
from dataclasses import dataclass

import httpx

from voicesaju.tts.chunker import DEFAULT_MAX_SENTENCE_CHARS, split_buffer
from voicesaju.tts.exceptions import (
    TTSFallthroughSignal,
    TTSFirstChunkTimeout,
    TTSMidStreamTimeout,
)

# --- Budgets / tuning knobs (defaults; callers can override) -----------

# NFR-002 budgets the first audible byte at ≤ 1.5s p95. The 5.0s here
# is the *hard* failure threshold from Architecture §8.3 — anything
# slower means we degrade to text-only mode.
DEFAULT_FIRST_CHUNK_TIMEOUT_SECONDS: float = 5.0

# Per-sentence mid-stream chunk timeout. Architecture §8.3 row 2.
DEFAULT_MID_STREAM_TIMEOUT_SECONDS: float = 3.0

# Cumulative 429-breach budget. After this many seconds of being
# rate-limited the client raises ``TTSFallthroughSignal`` so the
# pipeline can switch the reading to text-only.
DEFAULT_BACKOFF_BREACH_SECONDS: float = 8.0

# Concurrency cap. DEP-01 in `business_analysis §4.4` notes Supertone's
# tiered limits at 20–60 req/min — 4 in-flight requests keeps comfortable
# headroom while still parallelising sentence synthesis.
DEFAULT_CONCURRENCY: int = 4

# Default Supertone endpoint. Real Phase-2 host comes from
# ``SUPERTONE_BASE_URL`` env (or defaults to the documented endpoint
# in DEP-01). Tests patch the URL via ``base_url=``.
DEFAULT_BASE_URL: str = "https://api.supertone.ai/v1"

# 429 backoff base + cap (exponential with jitter).
_BACKOFF_BASE_SECONDS: float = 0.5
_BACKOFF_CAP_SECONDS: float = 4.0


@dataclass(slots=True, frozen=True)
class AudioChunk:
    """One synthesized audio fragment yielded by the streaming client.

    The pipeline consumes these in source order and routes each to the
    R2 upload + SSE ``audio_ready`` event (ISSUE-038, ISSUE-039).
    """

    # Audio bytes for this chunk. For MockTTSAdapter under Phase-1
    # this is a complete silent MP3 stream; for the real Supertone
    # client it's a single SSE data event payload.
    data: bytes
    # Zero-based ordinal so the client can re-order if the underlying
    # transport ever delivers chunks out of order (mainly belt-and-
    # suspenders for the real HTTPX streaming path).
    seq: int
    # Source sentence text that produced this chunk. Useful for log
    # correlation + SSE ``subtitle`` events.
    sentence: str
    # Voice id the chunk was rendered under. Echoed so the pipeline
    # can attach it to the audio metadata without re-threading state.
    voice_id: str


# ----------------------------------------------------------------------
# Client
# ----------------------------------------------------------------------


class SupertoneClient:
    """Structural Supertone streaming client.

    Owns the ``httpx.AsyncClient``, the in-flight concurrency cap (a
    :class:`asyncio.Semaphore`) and the cumulative 429-breach window.
    Construct one per reading-pipeline invocation; ``aclose()`` after
    the pipeline ends so the underlying connection pool is released.

    The class is also usable as an async context manager::

        async with SupertoneClient(api_key="…") as client:
            async for chunk in client.synthesize_stream(stream, "nuna"):
                ...
    """

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str = DEFAULT_BASE_URL,
        first_chunk_timeout_seconds: float = DEFAULT_FIRST_CHUNK_TIMEOUT_SECONDS,
        mid_stream_timeout_seconds: float = DEFAULT_MID_STREAM_TIMEOUT_SECONDS,
        backoff_breach_seconds: float = DEFAULT_BACKOFF_BREACH_SECONDS,
        concurrency: int = DEFAULT_CONCURRENCY,
        max_sentence_chars: int = DEFAULT_MAX_SENTENCE_CHARS,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        # ``api_key`` may be ``None`` at construction (callers might
        # build the client up-front then resolve credentials per-
        # request via env). We re-validate at request time so the app
        # still boots under TTS_PROVIDER=supertone without a key.
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._first_chunk_timeout = first_chunk_timeout_seconds
        self._mid_stream_timeout = mid_stream_timeout_seconds
        self._backoff_breach = backoff_breach_seconds
        self._max_sentence_chars = max_sentence_chars
        # Bound the in-flight count so we don't trip Supertone's tier
        # rate limit. Sentences arrive faster than they synthesize, so
        # this is the back-pressure point.
        self._semaphore = asyncio.Semaphore(concurrency)
        # ``transport`` lets tests inject ``httpx.MockTransport`` /
        # respx. In production, leaving it ``None`` lets httpx pick
        # the default async transport.
        self._client = httpx.AsyncClient(
            transport=transport,
            timeout=httpx.Timeout(
                connect=5.0,
                read=mid_stream_timeout_seconds,
                write=5.0,
                pool=5.0,
            ),
        )

    # -- lifecycle ------------------------------------------------------

    async def aclose(self) -> None:
        """Release the underlying connection pool."""
        await self._client.aclose()

    async def __aenter__(self) -> SupertoneClient:
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.aclose()

    # -- public api ----------------------------------------------------

    async def synthesize_stream(
        self,
        text_stream: AsyncIterable[str],
        voice_id: str,
    ) -> AsyncIterator[AudioChunk]:
        """Stream :class:`AudioChunk` objects from a stream of text fragments.

        Args:
            text_stream: Async-iterable of text fragments (typically
                from the LLM SSE stream). Fragments are buffered and
                split into sentences by :func:`chunk_sentences`.
            voice_id: Supertone voice id (e.g. ``voice_id_nuna_v1``).
                Sent unchanged in the request body.

        Yields:
            :class:`AudioChunk` per sentence, in source order.

        Raises:
            TTSFirstChunkTimeout: First chunk did not arrive within
                ``first_chunk_timeout_seconds``.
            TTSMidStreamTimeout: A mid-stream sentence exceeded
                ``mid_stream_timeout_seconds``.
            TTSFallthroughSignal: 429 backoff cumulative breach
                exceeded ``backoff_breach_seconds``.
            RuntimeError: ``SUPERTONE_API_KEY`` is missing at request
                time (only when the real path is hit).
        """
        self._require_api_key()
        seq = 0
        first_chunk_emitted = False
        breach_started_at: float | None = None
        text_buffer = ""

        async for fragment in text_stream:
            text_buffer += fragment
            # ``split_buffer`` returns ``(completed, remainder)``. The
            # remainder is verbatim (no leading-space stripping) so a
            # follow-up fragment's leading content concatenates cleanly
            # — critical for LLM SSE streams that split on arbitrary
            # byte boundaries (e.g. mid-word, mid-space).
            sentences, text_buffer = split_buffer(
                text_buffer, max_chars=self._max_sentence_chars
            )

            for sentence in sentences:
                async for chunk in self._stream_one_sentence(
                    sentence=sentence,
                    voice_id=voice_id,
                    seq=seq,
                    is_first=not first_chunk_emitted,
                    breach_state=_BreachState(started_at=breach_started_at),
                ):
                    first_chunk_emitted = True
                    yield chunk
                seq += 1

        # Flush whatever is left in the buffer after the upstream
        # text-stream finishes. Pipelines occasionally end without a
        # trailing terminator (e.g. follow-up answers that the LLM cuts
        # off at a clean clause boundary).
        if text_buffer.strip():
            async for chunk in self._stream_one_sentence(
                sentence=text_buffer.strip(),
                voice_id=voice_id,
                seq=seq,
                is_first=not first_chunk_emitted,
                breach_state=_BreachState(started_at=breach_started_at),
            ):
                yield chunk

    # -- internals ----------------------------------------------------

    def _require_api_key(self) -> None:
        """Resolve + validate the api key at the first network call.

        Construction must not fail when the env is empty (the app must
        still boot under ``TTS_PROVIDER=supertone`` before ISSUE-036
        provisioning ships). Instead, we raise here at request time
        with an actionable message.
        """
        if self._api_key:
            return
        env_key = os.environ.get("SUPERTONE_API_KEY")
        if env_key:
            self._api_key = env_key
            return
        raise RuntimeError(
            "TTS_PROVIDER=supertone requires ISSUE-036 provisioning: "
            "set SUPERTONE_API_KEY in the environment, or fall back to "
            "TTS_PROVIDER=mock for the Phase-1 PoC stack."
        )

    async def _stream_one_sentence(
        self,
        *,
        sentence: str,
        voice_id: str,
        seq: int,
        is_first: bool,
        breach_state: _BreachState,
    ) -> AsyncIterator[AudioChunk]:
        """Issue one synthesize request, applying timeout + 429 backoff."""
        timeout = self._first_chunk_timeout if is_first else self._mid_stream_timeout
        async with self._semaphore:
            try:
                data = await asyncio.wait_for(
                    self._request_with_backoff(
                        sentence=sentence,
                        voice_id=voice_id,
                        breach_state=breach_state,
                    ),
                    timeout=timeout,
                )
            except TimeoutError as exc:
                if is_first:
                    raise TTSFirstChunkTimeout(
                        f"First TTS chunk did not arrive within {timeout}s. "
                        "Pipeline must degrade to text-only (FR-034)."
                    ) from exc
                raise TTSMidStreamTimeout(
                    f"Mid-stream TTS chunk for sentence #{seq} did not "
                    f"arrive within {timeout}s."
                ) from exc

        yield AudioChunk(
            data=data,
            seq=seq,
            sentence=sentence,
            voice_id=voice_id,
        )

    async def _request_with_backoff(
        self,
        *,
        sentence: str,
        voice_id: str,
        breach_state: _BreachState,
    ) -> bytes:
        """POST one synthesize request, retrying on 429 with backoff.

        Cumulative breach is tracked across retries. If the rolling
        window exceeds ``backoff_breach_seconds`` we raise
        ``TTSFallthroughSignal`` so the pipeline can switch to text-
        only mode (FR-034 row 3).
        """
        attempt = 0
        while True:
            response = await self._post_synthesize(sentence, voice_id)
            if response.status_code == 429:
                if breach_state.started_at is None:
                    breach_state.started_at = time.monotonic()
                elapsed = time.monotonic() - breach_state.started_at
                if elapsed > self._backoff_breach:
                    raise TTSFallthroughSignal(
                        f"Supertone 429 backoff breached {self._backoff_breach}s "
                        "budget — pipeline degrades to text-only (FR-034)."
                    )
                await asyncio.sleep(_compute_backoff(attempt))
                attempt += 1
                continue
            response.raise_for_status()
            # Reset the breach window once a request succeeds so a
            # later, unrelated 429 starts the budget fresh.
            breach_state.started_at = None
            return response.content

    async def _post_synthesize(
        self,
        sentence: str,
        voice_id: str,
    ) -> httpx.Response:
        """Issue the actual HTTPS POST to Supertone.

        Pulled out so tests can mock just this method or rely on the
        ``httpx.MockTransport`` injected at construction time.
        """
        return await self._client.post(
            f"{self._base_url}/text-to-speech",
            json={"text": sentence, "voice_id": voice_id},
            headers={"Authorization": f"Bearer {self._api_key}"},
        )


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------


@dataclass(slots=True)
class _BreachState:
    """Mutable holder so the 429 breach timer survives across retries."""

    started_at: float | None


def _compute_backoff(attempt: int) -> float:
    """Exponential backoff with jitter (capped at ``_BACKOFF_CAP_SECONDS``)."""
    base = min(_BACKOFF_BASE_SECONDS * (2**attempt), _BACKOFF_CAP_SECONDS)
    # ``random.random()`` here is *not* a security boundary — just full
    # jitter so concurrent clients don't synchronise their retries
    # (AWS Architecture Blog "Exponential Backoff and Jitter").
    return base * random.random()  # noqa: S311


def _ends_with_terminator(text: str) -> bool:
    """``True`` if *text* ends in a sentence terminator + optional space."""
    stripped = text.rstrip()
    if not stripped:
        return False
    return stripped[-1] in ".?!…"


# ----------------------------------------------------------------------
# Module-level convenience wrapper
# ----------------------------------------------------------------------


async def synthesize_stream(
    text_stream: AsyncIterable[str],
    voice_id: str,
    *,
    api_key: str | None = None,
    base_url: str = DEFAULT_BASE_URL,
    transport: httpx.AsyncBaseTransport | None = None,
) -> AsyncIterator[AudioChunk]:
    """Module-level convenience that owns the :class:`SupertoneClient`.

    Matches the public interface called out in the ISSUE-037 spec:
    ``voicesaju.tts.supertone_client.synthesize_stream``. Use this when
    the caller doesn't need to reuse a client across multiple readings.
    """
    async with SupertoneClient(
        api_key=api_key,
        base_url=base_url,
        transport=transport,
    ) as client:
        async for chunk in client.synthesize_stream(text_stream, voice_id):
            yield chunk


__all__ = [
    "DEFAULT_BACKOFF_BREACH_SECONDS",
    "DEFAULT_BASE_URL",
    "DEFAULT_CONCURRENCY",
    "DEFAULT_FIRST_CHUNK_TIMEOUT_SECONDS",
    "DEFAULT_MID_STREAM_TIMEOUT_SECONDS",
    "AudioChunk",
    "SupertoneClient",
    "synthesize_stream",
]
