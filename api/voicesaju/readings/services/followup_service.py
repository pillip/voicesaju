"""Follow-up question orchestration (ISSUE-041).

Two responsibilities split across pure functions so the FastAPI router
stays thin:

1. ``suggest_followups`` — given a completed reading, return three
   questions. Tries the LLM adapter first; if it raises or returns
   fewer than three usable questions, falls back to a hardcoded
   category-specific copy bank (FR-009 fallback contract).

2. ``run_followup_answer`` — given a reading + slot index + question,
   stream the answer back as SSE bytes (``subtitle`` + ``audio_ready``
   + ``end`` events), persisting the per-slot ``ReadingFollowup`` row
   with the answer text and the first-chunk's R2 key.

Both helpers are free functions so unit tests inject mock LLM / TTS /
storage adapters without instantiating any class.

PRD-Ref: FR-009 (3-question suggestions), FR-010 (single-paragraph
answer 25-45s), NFR-004 (first audio chunk within 2s for follow-up).
Architecture-Ref: §6.3 (SSE event vocabulary), §7.1 (LLM routing).
"""

from __future__ import annotations

import json
import logging
import time
from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession

from voicesaju.adapters.llm import LLMAdapter
from voicesaju.adapters.tts import TTSAdapter
from voicesaju.db.models.reading_followups import ReadingFollowup
from voicesaju.llm.guardrail.denylist import filter_chunk
from voicesaju.readings.services.pipeline_service import _sse_event
from voicesaju.storage.r2_client import R2Client
from voicesaju.tracing import tracer

logger = logging.getLogger(__name__)

# NFR-004: first audio chunk for a follow-up answer must reach the
# client within 2s. We instrument when violated; we do NOT fail.
FOLLOWUP_FIRST_AUDIO_BUDGET_SECONDS: float = 2.0

# FR-010: answer paragraph should land in the 25-45s window.
# Outside the window we log a structured warning; we do NOT truncate.
FOLLOWUP_ANSWER_MIN_DURATION_MS: int = 25_000
FOLLOWUP_ANSWER_MAX_DURATION_MS: int = 45_000

# Number of suggested questions per reading. The schema constrains
# ``slot_index BETWEEN 0 AND 2`` so the value must stay <= 3.
FOLLOWUP_SUGGEST_COUNT: int = 3

# Voice ID used for follow-up TTS. M2 ships the nuna persona only.
_FOLLOWUP_VOICE_ID = "voice-nuna-followup"


# ---------------------------------------------------------------------------
# Hardcoded fallback questions (FR-009 fallback contract)
# ---------------------------------------------------------------------------
#
# Three questions per supported reading category, picked to be broadly
# useful regardless of the specific saju chart. Korean copy is verbatim
# from docs/copy_guide.md follow-up scaffolds (M2 placeholder set —
# the canonical bank lives there once copy review lands).
_FALLBACK_QUESTIONS_BY_CATEGORY: dict[str, list[str]] = {
    "love": [
        "내년에 새로운 인연이 들어올 운이 있을까?",
        "지금 만나는 사람과의 관계는 어떻게 흘러갈까?",
        "내 마음을 정리하려면 뭘 먼저 봐야 할까?",
    ],
    "work": [
        "지금 하는 일이 나랑 잘 맞는지 봐줘.",
        "올해 안에 이직하면 어떻게 될까?",
        "내 강점이 가장 잘 살아나는 환경은 어디일까?",
    ],
    "money": [
        "올해 금전운은 어떻게 흘러가?",
        "투자에 적합한 시기는 언제일까?",
        "씀씀이를 어떻게 조절해야 모일까?",
    ],
}


def _fallback_questions(category: str) -> list[str]:
    """Return the canonical fallback list for *category*.

    Unknown categories fall back to ``love`` — chosen because the
    questions are the most generic, not because love is special.
    """
    return list(
        _FALLBACK_QUESTIONS_BY_CATEGORY.get(
            category, _FALLBACK_QUESTIONS_BY_CATEGORY["love"]
        )
    )


# ---------------------------------------------------------------------------
# suggest_followups — GET /api/v1/reading/{id}/followups
# ---------------------------------------------------------------------------


async def suggest_followups(
    *,
    reading_id: str,
    category: str,
    llm: LLMAdapter,
) -> list[str]:
    """Return three follow-up question candidates for *reading_id*.

    Strategy:
    1. Ask the LLM (Haiku 4.5 in prod, mock fixture in Phase-1) for a
       JSON list of questions tied to the reading's category.
    2. Parse the JSON; require exactly 3 non-empty strings.
    3. On ANY failure (adapter raises, parse fails, empty/short list),
       return the hardcoded fallback set for the category (FR-009 AC).

    The function never raises — fallback is always available.
    """
    prompt = _compose_followup_suggest_prompt(category=category)

    with tracer.start_span("followup.suggest") as span:
        span.set_attribute("reading_id", reading_id)
        span.set_attribute("category", category)
        try:
            chunks: list[str] = []
            async for chunk in llm.stream(
                prompt=prompt,
                # Route this through the FOLLOWUP_SUGGEST task kind in
                # the real adapter. For the mock the category=string is
                # what picks the fixture, so we keep the category itself.
                category=category,
                seed=f"followup-suggest:{reading_id}",
            ):
                chunks.append(chunk)
            raw = "".join(chunks).strip()
            parsed = _parse_questions_payload(raw)
            if len(parsed) >= FOLLOWUP_SUGGEST_COUNT:
                span.set_attribute("source", "llm")
                return parsed[:FOLLOWUP_SUGGEST_COUNT]
            # Short list → fall through to fallback. We treat <3 as a
            # parse failure to keep the contract simple.
            span.set_attribute("source", "fallback_short_list")
            span.set_attribute("llm_question_count", len(parsed))
        except Exception as exc:  # noqa: BLE001 — fallback is the contract
            span.set_attribute("source", "fallback_exception")
            span.set_attribute("error", repr(exc))
            logger.warning(
                "followup.suggest llm path failed reading_id=%s category=%s err=%r",
                reading_id,
                category,
                exc,
            )

        return _fallback_questions(category)


def _compose_followup_suggest_prompt(*, category: str) -> str:
    """Compose a JSON-shaped Haiku prompt for the suggest endpoint.

    Kept minimal — the MockLLMAdapter ignores the prompt entirely (it
    selects fixtures by category + seed). The real Haiku path will
    expand on this once the prompt-template module lands.
    """
    return (
        f"[task=followup_suggest] [category={category}] "
        "Return JSON array of exactly 3 follow-up question strings."
    )


def _parse_questions_payload(raw: str) -> list[str]:
    """Best-effort JSON / line-list parser for the suggest response.

    Accepts three shapes — the LLM occasionally drifts off-spec and we
    prefer to recover rather than fail to fallback:

    - ``["q1", "q2", "q3"]`` — canonical JSON array.
    - ``{"questions": ["q1", "q2", "q3"]}`` — wrapped envelope.
    - newline-separated bare strings — last-resort fallback.

    Returns the list of non-empty stripped strings (no length cap).
    """
    if not raw:
        return []

    # 1. Canonical JSON array.
    try:
        loaded = json.loads(raw)
    except json.JSONDecodeError:
        loaded = None

    if isinstance(loaded, list):
        return [str(q).strip() for q in loaded if str(q).strip()]
    if isinstance(loaded, dict) and isinstance(loaded.get("questions"), list):
        return [str(q).strip() for q in loaded["questions"] if str(q).strip()]

    # 2. Newline-separated fallback (rare LLM drift case).
    candidates = [line.strip(" -•\t") for line in raw.splitlines() if line.strip()]
    return [c for c in candidates if c]


# ---------------------------------------------------------------------------
# run_followup_answer — POST /api/v1/reading/{id}/followups/{index}
# ---------------------------------------------------------------------------


async def run_followup_answer(
    *,
    reading_id: str,
    slot_index: int,
    question_text: str,
    category: str,
    llm: LLMAdapter,
    tts: TTSAdapter,
    r2: R2Client,
    db_session: AsyncSession,
    followup_row: ReadingFollowup,
) -> AsyncIterator[bytes]:
    """Stream the SSE answer for *slot_index* on *reading_id*.

    Pipeline stages (each wrapped in a tracing span):

    1. ``followup.llm_stream`` — Haiku 4.5 (mock fixture in Phase-1)
       streams sentences. Same guardrail pass as the main reading.
    2. ``followup.tts_stream`` + ``followup.r2_upload`` — feed each
       sentence to TTS, upload each MP3 chunk to R2 under
       ``audio/readings/<reading_id>/followups/<slot>/<seq:04d>.mp3``.
    3. Persist the row: first chunk's key lands on
       ``ReadingFollowup.audio_r2_key`` (so the replay path can find
       it without scanning storage); the accumulated answer text lands
       on ``answer_text`` once the LLM stream completes.

    Yields SSE-framed bytes consumable by ``StreamingResponse``.
    """
    started_at = time.perf_counter()
    first_audio_at: float | None = None
    chunk_seq = 0
    audio_offset_ms = 0
    answer_sentences: list[str] = []
    answer_audio_key: str | None = None

    prompt = _compose_followup_answer_prompt(category=category, question=question_text)

    with tracer.start_span("followup.answer") as span:
        span.set_attribute("reading_id", reading_id)
        span.set_attribute("slot_index", slot_index)
        span.set_attribute("category", category)

        async for raw_sentence in llm.stream(
            prompt=prompt,
            category=category,
            seed=f"followup-answer:{reading_id}:{slot_index}",
        ):
            # Guardrail (same as main pipeline).
            with tracer.start_span("followup.guardrail") as g_span:
                result = filter_chunk(raw_sentence, character="nuna")
                g_span.set_attribute("action", result.action)
                if result.hits:
                    g_span.set_attribute("hits", ",".join(result.hits))

            if result.action == "block":
                continue

            sentence = result.text
            answer_sentences.append(sentence)

            # Subtitle BEFORE audio_ready so the frontend scheduler
            # can pre-stage the cue (architecture §6.3).
            yield _sse_event(
                "subtitle",
                {"text": sentence, "audio_offset_ms": audio_offset_ms},
            )

            with tracer.start_span("followup.tts_stream") as tts_span:
                tts_span.set_attribute("reading_id", reading_id)
                tts_span.set_attribute("slot_index", slot_index)
                tts_span.set_attribute("sentence_chars", len(sentence))

                async for audio_chunk in tts.stream(
                    text=sentence, voice_id=_FOLLOWUP_VOICE_ID
                ):
                    chunk_key = _followup_chunk_key(
                        reading_id=reading_id,
                        slot_index=slot_index,
                        seq=chunk_seq,
                    )
                    with tracer.start_span("followup.r2_upload") as up_span:
                        chunk_url = await r2.put_object(chunk_key, audio_chunk)
                        up_span.set_attribute("seq", chunk_seq)
                        up_span.set_attribute("size_bytes", len(audio_chunk))

                    yield _sse_event(
                        "audio_ready",
                        {"seq": chunk_seq, "url": chunk_url},
                    )

                    if first_audio_at is None:
                        first_audio_at = time.perf_counter()
                        first_audio_latency = first_audio_at - started_at
                        answer_audio_key = chunk_key
                        if first_audio_latency > FOLLOWUP_FIRST_AUDIO_BUDGET_SECONDS:
                            with tracer.start_span(
                                "followup.first_audio_budget_violated"
                            ) as v_span:
                                v_span.set_attribute(
                                    "latency_seconds", first_audio_latency
                                )
                                v_span.set_attribute(
                                    "budget_seconds",
                                    FOLLOWUP_FIRST_AUDIO_BUDGET_SECONDS,
                                )

                    chunk_seq += 1
                    # MockTTSAdapter emits ~200ms chunks (matches main
                    # pipeline pacing). Real Supertone client will need
                    # the actual duration per chunk once it lands.
                    audio_offset_ms += 200

        # Terminal SSE event with total duration.
        total_duration_ms = audio_offset_ms
        span.set_attribute("duration_ms", total_duration_ms)
        span.set_attribute("chunk_count", chunk_seq)

        # FR-010: warn when the answer drifts outside the 25-45s window.
        # Phase-1 mock fixtures usually produce a much shorter audio
        # paragraph than the production target, so the warning fires
        # ~always in tests. That's expected — the warning is real
        # only once the production LLM + TTS chain is wired.
        if (
            total_duration_ms < FOLLOWUP_ANSWER_MIN_DURATION_MS
            or total_duration_ms > FOLLOWUP_ANSWER_MAX_DURATION_MS
        ):
            logger.warning(
                "followup.duration_out_of_band reading_id=%s slot=%d "
                "duration_ms=%d window=[%d, %d]",
                reading_id,
                slot_index,
                total_duration_ms,
                FOLLOWUP_ANSWER_MIN_DURATION_MS,
                FOLLOWUP_ANSWER_MAX_DURATION_MS,
            )

        yield _sse_event(
            "end",
            {
                "reading_id": reading_id,
                "slot_index": slot_index,
                "duration_ms": total_duration_ms,
            },
        )

    # Persist the row AFTER the SSE stream has flushed. SQLAlchemy is
    # OK to commit inside an async generator because the StreamingResponse
    # exits the iterator (and our `with tracer` blocks) before the
    # response closes; the session is owned by the route's Depends and
    # lives across this update.
    followup_row.answer_text = "\n".join(answer_sentences)
    if answer_audio_key is not None:
        followup_row.audio_r2_key = answer_audio_key
    await db_session.commit()


def _compose_followup_answer_prompt(*, category: str, question: str) -> str:
    """Compose the Haiku prompt for streaming the answer.

    Mock-friendly minimal template. The real Haiku path will replace
    this with a category-aware system block in the prompt-template
    module (out of scope for ISSUE-041).
    """
    return (
        f"[task=followup_answer] [category={category}] "
        f"[question={question!r}] Answer in one supportive paragraph."
    )


def _followup_chunk_key(*, reading_id: str, slot_index: int, seq: int) -> str:
    """Canonical R2 key for a per-slot chunk.

    Layout mirrors the main pipeline's
    ``audio/readings/<id>/chunks/<seq>.mp3`` so the same storage
    adapter, prefix scanner, and finalize worker patterns reuse
    transparently. Slot index is zero-padded to keep lexical sort =
    numeric sort for future replay (FR-028).
    """
    return f"audio/readings/{reading_id}/followups/{slot_index:01d}/{seq:04d}.mp3"


__all__ = [
    "FOLLOWUP_ANSWER_MAX_DURATION_MS",
    "FOLLOWUP_ANSWER_MIN_DURATION_MS",
    "FOLLOWUP_FIRST_AUDIO_BUDGET_SECONDS",
    "FOLLOWUP_SUGGEST_COUNT",
    "_fallback_questions",
    "_followup_chunk_key",
    "_parse_questions_payload",
    "run_followup_answer",
    "suggest_followups",
]
