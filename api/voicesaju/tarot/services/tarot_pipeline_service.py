"""Daily-tarot pipeline orchestrator (ISSUE-049).

End-to-end Phase-1 implementation of the M3 tarot flow:

    seed(date+subject) → tarot_card lookup → LLM stream (Haiku 4.5)
      → guardrail → TTS chunks → R2 upload (audio/tarot/...)
      → transcript persist → SSE emit

Structurally mirrors :mod:`voicesaju.readings.services.pipeline_service`
(ISSUE-039) — same SSE event vocabulary, same per-stage OTel spans,
same chunk-upload loop. The tarot-specific bits are:

* The card seed is derived from
  :func:`voicesaju.tarot.seed.daily_card_index` rather than the
  caller-supplied reading_id, and we look up the corresponding
  ``tarot_cards`` row for metadata.
* Audio chunks land under ``audio/tarot/{draw_id}/chunks/{seq:04d}.mp3``
  (note: ``tarot`` prefix, not ``readings``).
* The terminal SSE event carries ``draw_id`` (not ``reading_id``).
* On stream completion, the ``tarot_draws`` row's ``transcript`` and
  ``audio_r2_key`` fields are filled in so the daily-summary endpoint
  (ISSUE-052+) can return the same text without re-running the LLM.

Note on persistence: the Phase-1 ``TarotDraw`` model from ISSUE-016 does
NOT yet have ``transcript`` or ``audio_r2_key`` columns — those land in
ISSUE-052 (daily summary). For now the pipeline just emits the SSE
events and writes the audio chunks; transcript persistence is a
no-op pending schema work.

SSE event vocabulary (per ``docs/architecture.md`` §6.3):

- ``subtitle``    — ``{text, audio_offset_ms}``
- ``audio_ready`` — ``{seq, url}``
- ``end``         — ``{draw_id, duration_ms}``
- ``error``       — ``{code, message}``

Per-stage OTel spans are emitted via :mod:`voicesaju.tracing` (no-op
shim in Phase-1).
"""

from __future__ import annotations

import json
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from voicesaju.adapters.llm import LLMAdapter
from voicesaju.adapters.tts import TTSAdapter
from voicesaju.llm.guardrail.denylist import filter_chunk
from voicesaju.storage.r2_client import R2Client
from voicesaju.tracing import tracer

# NFR-003: first audio chunk must reach the client within 2s of the
# flip request. We log a structured event when this is violated; we
# do NOT fail the request. The instrumentation here is the source of
# truth for the production NFR — the TestClient buffering means
# tests can only assert a relaxed budget (see test_pipeline.py).
FIRST_AUDIO_BUDGET_SECONDS: float = 2.0

# Tarot Phase-1 uses the same persona voice as M2 readings since the
# product hasn't shipped a tarot-specific voice yet. Lives as a
# constant so the swap is one line when the voice catalogue grows.
_TAROT_VOICE_ID: str = "voice-nuna-default"

# Audio key prefix for tarot chunks. Mirrors the reading pipeline's
# ``audio/readings/{id}/chunks/`` layout but uses the ``tarot`` namespace
# so the worker that sweeps idle reading chunks (FR-028) doesn't touch
# tarot audio.
_AUDIO_PREFIX: str = "audio/tarot"


@dataclass(slots=True, frozen=True)
class TarotPipelineDeps:
    """Bundle of collaborators the tarot orchestrator needs.

    Symmetric to :class:`voicesaju.readings.services.pipeline_service.
    PipelineDeps` so a future refactor can fold the two pipelines into
    one generic orchestrator without disturbing the router layer.
    """

    llm: LLMAdapter
    tts: TTSAdapter
    r2: R2Client
    db_session: AsyncSession


def _sse_event(event: str, data: dict) -> bytes:
    """Format ``data`` as a single SSE event block.

    Identical framing to the reading pipeline so the frontend SSE
    parser doesn't need to special-case tarot.
    """
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    return f"event: {event}\ndata: {payload}\n\n".encode()


def _tarot_chunk_url_key(draw_id: str, seq: int) -> str:
    """Return the storage key for the *seq*-th audio chunk of *draw_id*."""
    return f"{_AUDIO_PREFIX}/{draw_id}/chunks/{seq:04d}.mp3"


async def _put_tarot_chunk(r2: R2Client, draw_id: str, seq: int, data: bytes) -> str:
    """Upload a tarot audio chunk and return its storage URL.

    Wraps ``R2Client.put_object`` directly because ``R2Client.put_chunk``
    is hard-coded to the ``audio/readings/`` prefix. The tarot domain
    has its own key namespace (see module docstring), so we bypass the
    reading-specific helper.
    """
    return await r2.put_object(_tarot_chunk_url_key(draw_id, seq), data)


async def run_tarot_pipeline(
    *,
    draw_id: str,
    card_index: int,
    deps: TarotPipelineDeps,
) -> AsyncIterator[bytes]:
    """Drive the tarot LLM→guardrail→TTS→R2 pipeline and yield SSE bytes.

    Stages (each wrapped in a tracing span):

    1. **llm_stream** — Haiku-class LLM yields tarot reading sentences.
       Phase-1: ``MockLLMAdapter`` reads from
       ``tests/fixtures/llm/tarot/{N}.txt`` deterministically on
       ``seed=draw_id``. The category passed to the adapter is
       ``"tarot"`` so the mock picks the tarot fixture directory.
    2. **guardrail** — :func:`voicesaju.llm.guardrail.denylist.filter_chunk`
       runs per sentence; blocked sentences are silently dropped.
    3. **tts_stream** — MockTTSAdapter emits ~10 chunks per sentence
       with 200ms pacing; each chunk is uploaded immediately so the
       SSE consumer can start playback before the full stream completes.
    4. **r2_upload** — chunks land at
       ``audio/tarot/{draw_id}/chunks/{seq:04d}.mp3``.
    5. **sse_emit** — terminal ``end`` event carries draw_id +
       duration_ms (cumulative ``audio_offset_ms``).

    Args:
        draw_id: The PK of the ``tarot_draws`` row this stream
            corresponds to. Used both as the LLM seed (deterministic
            fixture selection in the mock path) and as the storage
            prefix for audio chunks.
        card_index: Major Arcana index 0..21. Currently only logged on
            the OTel span — the LLM picks the fixture from
            ``seed=draw_id``, not from the card index. When the real
            Haiku adapter lands it can use this in the system prompt.
        deps: Injected collaborators (LLM, TTS, R2, DB).

    Yields:
        SSE-framed bytes (``event:``/``data:``/blank line). The caller
        wraps this in a ``StreamingResponse`` with
        ``media_type="text/event-stream"``.
    """
    pipeline_started_at = time.perf_counter()
    first_audio_emitted_at: float | None = None
    chunk_seq = 0
    audio_offset_ms = 0

    # Stage 0 — record the card we're reading for (observability only;
    # MockLLM picks the fixture from ``seed``).
    with tracer.start_span("tarot_pipeline.card_lookup") as span:
        span.set_attribute("draw_id", draw_id)
        span.set_attribute("card_index", card_index)

    # Stage 1 — LLM stream + per-sentence guardrail + TTS + R2 upload.
    with tracer.start_span("tarot_pipeline.llm_stream") as llm_span:
        llm_span.set_attribute("draw_id", draw_id)
        llm_span.set_attribute("card_index", card_index)

        async for raw_sentence in deps.llm.stream(
            prompt=_compose_prompt(card_index=card_index),
            category="tarot",
            seed=draw_id,
        ):
            # Stage 2 — guardrail. Substitute / block / pass.
            with tracer.start_span("tarot_pipeline.guardrail") as g_span:
                result = filter_chunk(raw_sentence, character="nuna")
                g_span.set_attribute("action", result.action)
                if result.hits:
                    g_span.set_attribute("hits", ",".join(result.hits))

            if result.action == "block":
                continue

            sentence = result.text

            # Emit subtitle BEFORE the audio chunk lands so the
            # frontend's playhead scheduler is ready when the chunk
            # URL is fetchable.
            yield _sse_event(
                "subtitle",
                {"text": sentence, "audio_offset_ms": audio_offset_ms},
            )

            # Stage 3+4 — TTS chunks + R2 upload per chunk.
            with tracer.start_span("tarot_pipeline.tts_stream") as tts_span:
                tts_span.set_attribute("draw_id", draw_id)
                tts_span.set_attribute("sentence_chars", len(sentence))

                async for audio_chunk in deps.tts.stream(
                    text=sentence, voice_id=_TAROT_VOICE_ID
                ):
                    with tracer.start_span("tarot_pipeline.r2_upload") as up_span:
                        chunk_url = await _put_tarot_chunk(
                            deps.r2, draw_id, chunk_seq, audio_chunk
                        )
                        up_span.set_attribute("seq", chunk_seq)
                        up_span.set_attribute("size_bytes", len(audio_chunk))

                    yield _sse_event(
                        "audio_ready",
                        {"seq": chunk_seq, "url": chunk_url},
                    )

                    if first_audio_emitted_at is None:
                        first_audio_emitted_at = time.perf_counter()
                        first_audio_latency = (
                            first_audio_emitted_at - pipeline_started_at
                        )
                        if first_audio_latency > FIRST_AUDIO_BUDGET_SECONDS:
                            # NFR-003 budget exceeded — instrument-only,
                            # do NOT fail the request. The OTel span is
                            # the source of truth for the production
                            # alerting path.
                            with tracer.start_span(
                                "tarot_pipeline.first_audio_budget_violated"
                            ) as v_span:
                                v_span.set_attribute(
                                    "latency_seconds", first_audio_latency
                                )
                                v_span.set_attribute(
                                    "budget_seconds",
                                    FIRST_AUDIO_BUDGET_SECONDS,
                                )

                    chunk_seq += 1
                    audio_offset_ms += 200

    # Stage 5 — terminal SSE event.
    with tracer.start_span("tarot_pipeline.sse_emit_end") as end_span:
        total_duration_ms = audio_offset_ms
        end_span.set_attribute("draw_id", draw_id)
        end_span.set_attribute("duration_ms", total_duration_ms)
        end_span.set_attribute("chunk_count", chunk_seq)
        yield _sse_event(
            "end",
            {"draw_id": draw_id, "duration_ms": total_duration_ms},
        )


def _compose_prompt(*, card_index: int) -> str:
    """Build the LLM prompt for the given card.

    Phase-1 keeps this minimal — the MockLLMAdapter ignores the prompt
    entirely (selects fixtures by category + seed). When the real
    Anthropic Haiku adapter lands the template lives in
    ``voicesaju.llm.prompts`` so edits can ship without touching the
    pipeline.
    """
    return f"[card_index={card_index}] Provide a brief, supportive daily tarot reading."


__all__ = [
    "FIRST_AUDIO_BUDGET_SECONDS",
    "TarotPipelineDeps",
    "run_tarot_pipeline",
]
