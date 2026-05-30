"""Reading pipeline orchestrator (ISSUE-039).

End-to-end Phase-1 implementation of the M2 reading flow:

    chart_lookup → LLM stream → guardrail → TTS chunks → R2 upload → SSE emit

The orchestrator is intentionally a free function (not a class) — every
collaborator is injected so the same routine can run hermetically in
unit tests with mocked adapters, and identically in production with the
real LLM / TTS / R2 clients.

SSE event vocabulary (per ``docs/architecture.md`` §6.3):

- ``subtitle``    — ``{text, audio_offset_ms}`` — the next sentence to
                    display, anchored to the audio playhead.
- ``audio_ready`` — ``{seq, url}`` — a new TTS chunk has been written
                    to storage and is ready for the player to fetch.
- ``end``         — ``{reading_id, duration_ms}`` — terminal event;
                    the SSE response closes immediately after.
- ``error``       — ``{code, message}`` — recoverable failure mid-stream
                    (e.g. guardrail blocks the entire output, TTS fails).

Per-stage OTel spans are emitted via :mod:`voicesaju.tracing` (no-op
shim in Phase-1; swaps to a real exporter once observability lands).
"""

from __future__ import annotations

import json
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from voicesaju.adapters.llm import LLMAdapter
from voicesaju.adapters.tts import TTSAdapter
from voicesaju.jobs.worker import InMemoryQueue
from voicesaju.llm.guardrail.denylist import filter_chunk
from voicesaju.storage.r2_client import R2Client
from voicesaju.tracing import tracer

# NFR-001: first audio chunk must reach the client within 3s of stream
# start. We log a structured event when this is violated; we do NOT
# fail the request — the user still gets the reading, just with a
# warning in the audit log.
FIRST_AUDIO_BUDGET_SECONDS: float = 3.0

# Per-character TTS voice id passed to the TTS adapter. M2 only ships
# the nuna persona; dosa lands in a later milestone.
_VOICE_ID_BY_CHARACTER: dict[str, str] = {
    "nuna": "voice-nuna-default",
}

_DEFAULT_VOICE_ID = "voice-nuna-default"


@dataclass(slots=True, frozen=True)
class PipelineDeps:
    """Bundle of collaborators the orchestrator needs.

    Wrapped in a dataclass so the router can build it once per request
    and the orchestrator stays free-function (no class state).
    """

    llm: LLMAdapter
    tts: TTSAdapter
    r2: R2Client
    queue: InMemoryQueue
    db_session: AsyncSession


def _sse_event(event: str, data: dict) -> bytes:
    """Format ``data`` as a single SSE event block.

    The framing matches the WHATWG spec: ``event: NAME\\ndata: JSON\\n\\n``.
    Every field is a single line — we serialise ``data`` with
    ``ensure_ascii=False`` so Korean copy survives the round trip
    untouched.
    """
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    return f"event: {event}\ndata: {payload}\n\n".encode()


async def run_pipeline(
    *,
    reading_id: str,
    category: str,
    character_key: str,
    deps: PipelineDeps,
) -> AsyncIterator[bytes]:
    """Drive the chart→LLM→guardrail→TTS→R2 pipeline and yield SSE bytes.

    Stages (each wrapped in a tracing span):

    1. **chart_lookup** — picks the reading seed. M2 uses ``reading_id``
       directly as the seed so the mock LLM yields a deterministic
       fixture per reading. The real path (Phase-2) will pull the
       cached SajuChart via :func:`voicesaju.saju.engine.compute_chart`.
    2. **llm_stream** — yields LLM sentences with deny-list filtering.
       Each sentence is paired with an audio_offset_ms anchored to the
       cumulative TTS playback duration so the frontend's NFR-015
       subtitle scheduler stays in sync.
    3. **guardrail** — :func:`voicesaju.llm.guardrail.denylist.filter_chunk`
       runs on each sentence. ``substitute`` emits the rewritten text;
       ``block`` drops the sentence entirely (logged via OTel attr).
    4. **tts_stream** — feeds the (possibly rewritten) sentence to the
       TTS adapter and accumulates the streamed MP3 chunks per
       sentence. We emit one ``audio_ready`` event per chunk after the
       chunk is persisted to storage.
    5. **r2_upload** — every TTS chunk is uploaded under the canonical
       key ``audio/readings/<reading_id>/chunks/<seq:04d>.mp3`` via
       :meth:`R2Client.put_chunk`. The chunk's signed URL flows into
       the ``audio_ready`` SSE event.
    6. **sse_emit** — terminal ``end`` event carries the total duration
       (approximated as ``seq * 200ms`` in Phase-1 — matches
       ``MockTTSAdapter`` pacing).

    Finally a ``finalize_audio`` job is enqueued so the worker stitches
    the chunks into ``main.mp3`` (FR-028 replay path).

    Returns:
        An async byte iterator producing SSE-framed events. The caller
        wraps this in a ``StreamingResponse`` with
        ``media_type="text/event-stream"``.
    """
    pipeline_started_at = time.perf_counter()
    first_audio_emitted_at: float | None = None
    chunk_seq = 0
    audio_offset_ms = 0

    # Stage 1 — chart_lookup. The mock LLM uses ``seed`` to pick a
    # deterministic fixture; the seed is the reading_id so re-running a
    # reading in a debugger produces stable output.
    with tracer.start_span("pipeline.chart_lookup") as span:
        span.set_attribute("reading_id", reading_id)
        span.set_attribute("category", category)
        seed = reading_id

    # Stage 2 — LLM stream + per-sentence guardrail + TTS + R2 upload.
    voice_id = _VOICE_ID_BY_CHARACTER.get(character_key, _DEFAULT_VOICE_ID)

    with tracer.start_span("pipeline.llm_stream") as llm_span:
        llm_span.set_attribute("reading_id", reading_id)
        llm_span.set_attribute("category", category)

        async for raw_sentence in deps.llm.stream(
            prompt=_compose_prompt(category=category, character_key=character_key),
            category=category,
            seed=seed,
        ):
            # Stage 3 — guardrail. Substitute / block / pass.
            with tracer.start_span("pipeline.guardrail") as g_span:
                result = filter_chunk(raw_sentence, character=character_key)
                g_span.set_attribute("action", result.action)
                if result.hits:
                    g_span.set_attribute("hits", ",".join(result.hits))

            if result.action == "block":
                # Drop the sentence — do NOT emit a subtitle or TTS for
                # this chunk; the user sees a small gap rather than the
                # blocked text. Future work can emit a generic apology.
                continue

            sentence = result.text

            # Emit subtitle event BEFORE the audio chunk lands so the
            # frontend's subtitle scheduler can set up the playhead
            # cue before the chunk is fetchable. Architecture §6.3.
            yield _sse_event(
                "subtitle",
                {"text": sentence, "audio_offset_ms": audio_offset_ms},
            )

            # Stage 4+5 — TTS chunks + R2 upload per chunk.
            with tracer.start_span("pipeline.tts_stream") as tts_span:
                tts_span.set_attribute("reading_id", reading_id)
                tts_span.set_attribute("sentence_chars", len(sentence))

                async for audio_chunk in deps.tts.stream(
                    text=sentence, voice_id=voice_id
                ):
                    with tracer.start_span("pipeline.r2_upload") as up_span:
                        chunk_url = await deps.r2.put_chunk(
                            reading_id=reading_id,
                            seq=chunk_seq,
                            data=audio_chunk,
                        )
                        up_span.set_attribute("seq", chunk_seq)
                        up_span.set_attribute("size_bytes", len(audio_chunk))

                    # SSE emit — audio_ready carries the chunk URL.
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
                            # Log via tracing — see Phase-2 OTel
                            # exporter wiring. Per ISSUE-039 spec we do
                            # NOT fail the request even when the budget
                            # is blown; we just instrument.
                            with tracer.start_span(
                                "pipeline.first_audio_budget_violated"
                            ) as v_span:
                                v_span.set_attribute(
                                    "latency_seconds", first_audio_latency
                                )
                                v_span.set_attribute(
                                    "budget_seconds", FIRST_AUDIO_BUDGET_SECONDS
                                )

                    chunk_seq += 1
                    # MockTTSAdapter emits 200ms-equivalent chunks. We
                    # advance the playhead so subsequent subtitle
                    # events anchor correctly.
                    audio_offset_ms += 200

    # Stage 6 — terminal SSE event.
    with tracer.start_span("pipeline.sse_emit_end") as end_span:
        total_duration_ms = audio_offset_ms
        end_span.set_attribute("reading_id", reading_id)
        end_span.set_attribute("duration_ms", total_duration_ms)
        end_span.set_attribute("chunk_count", chunk_seq)
        yield _sse_event(
            "end",
            {"reading_id": reading_id, "duration_ms": total_duration_ms},
        )

    # Enqueue finalize_audio so the worker stitches main.mp3 (FR-028).
    # In Phase-1 the queue is an InMemoryQueue; in prod, arq's Redis
    # poll-loop drains the same registry.
    await deps.queue.enqueue(
        "finalize_audio",
        reading_id,
        session=deps.db_session,
        duration_ms=total_duration_ms or 1000,
    )


def _compose_prompt(*, category: str, character_key: str) -> str:
    """Build the LLM prompt for the given category + persona.

    Phase-1 keeps this **deliberately minimal** — the MockLLMAdapter
    ignores the prompt entirely (selects fixtures by category + seed),
    so any string works. When the real Anthropic adapter lands the
    template lives in a separate ``voicesaju.llm.prompts`` module so
    edits can ship without touching the pipeline.
    """
    return (
        f"[character={character_key}] [category={category}] "
        "Provide a brief, supportive saju reading."
    )


__all__ = [
    "FIRST_AUDIO_BUDGET_SECONDS",
    "PipelineDeps",
    "run_pipeline",
]
