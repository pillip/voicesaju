"""Unit tests for ``SupertoneClient`` (ISSUE-037).

Covers each AC explicitly with mocked HTTPX transport (zero real
network). Real-Supertone provisioning is gated behind ISSUE-036; these
tests must remain hermetic.

ACs:
1. Sentences yielded as AudioChunk in source order (mocked SSE).
2. First chunk doesn't arrive in 5s → TTSFirstChunkTimeout.
3. 429 → exponential backoff; > 8s breach → TTSFallthroughSignal.
4. voice_id propagated to the request body.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import httpx
import pytest

from voicesaju.tts.exceptions import (
    TTSFallthroughSignal,
    TTSFirstChunkTimeout,
)
from voicesaju.tts.supertone_client import (
    AudioChunk,
    SupertoneClient,
)

# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------


async def _text_stream(*fragments: str) -> AsyncIterator[str]:
    """Tiny helper: async-iterate over the given fragments synchronously."""
    for fragment in fragments:
        yield fragment


def _mock_transport(handler):  # type: ignore[no-untyped-def]
    """Wrap a sync request handler into ``httpx.MockTransport``."""
    return httpx.MockTransport(handler)


# ----------------------------------------------------------------------
# AC #4 — voice_id propagation
# ----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_voice_id_propagated_to_request_body() -> None:
    """AC #4: ``voice_id`` MUST be sent verbatim in the Supertone payload."""
    received_payloads: list[dict[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        import json as _json

        received_payloads.append(_json.loads(request.content))
        return httpx.Response(200, content=b"\xff\xfb\x00\x00")

    client = SupertoneClient(
        api_key="test-key",
        transport=_mock_transport(handler),
    )
    try:
        chunks: list[AudioChunk] = []
        async for chunk in client.synthesize_stream(
            _text_stream("안녕하세요."),
            voice_id="voice_id_nuna_v1",
        ):
            chunks.append(chunk)
    finally:
        await client.aclose()

    assert len(received_payloads) == 1
    assert received_payloads[0]["voice_id"] == "voice_id_nuna_v1"
    assert received_payloads[0]["text"] == "안녕하세요."
    assert len(chunks) == 1
    assert chunks[0].voice_id == "voice_id_nuna_v1"
    assert chunks[0].sentence == "안녕하세요."
    assert chunks[0].data == b"\xff\xfb\x00\x00"
    assert chunks[0].seq == 0


# ----------------------------------------------------------------------
# AC #1 — sentences yielded in source order
# ----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_chunks_yielded_in_source_order() -> None:
    """AC #1: each sentence's AudioChunk MUST arrive in source order."""
    call_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        return httpx.Response(200, content=f"audio-{call_count}".encode())

    client = SupertoneClient(
        api_key="k",
        transport=_mock_transport(handler),
    )
    try:
        out: list[AudioChunk] = []
        async for chunk in client.synthesize_stream(
            _text_stream("첫 문장. 두 번째. 세 번째!"),
            voice_id="v1",
        ):
            out.append(chunk)
    finally:
        await client.aclose()

    assert [c.sentence for c in out] == [
        "첫 문장.",
        "두 번째.",
        "세 번째!",
    ]
    assert [c.seq for c in out] == [0, 1, 2]


@pytest.mark.asyncio
async def test_audio_chunk_carries_voice_id_field() -> None:
    """Every yielded ``AudioChunk`` MUST echo its ``voice_id``."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"x")

    client = SupertoneClient(
        api_key="k",
        transport=_mock_transport(handler),
    )
    try:
        chunks: list[AudioChunk] = []
        async for chunk in client.synthesize_stream(
            _text_stream("문장 하나."),
            voice_id="voice_id_dosa_v1",
        ):
            chunks.append(chunk)
    finally:
        await client.aclose()

    assert all(c.voice_id == "voice_id_dosa_v1" for c in chunks)


# ----------------------------------------------------------------------
# AC #2 — first-chunk timeout
# ----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_first_chunk_timeout_raises_tts_first_chunk_timeout() -> None:
    """AC #2: First chunk does not arrive in budget → TTSFirstChunkTimeout."""
    import asyncio

    async def slow_handler(request: httpx.Request) -> httpx.Response:
        # Sleep longer than the configured budget. The wait_for() in
        # the client will cancel us before we ever return.
        await asyncio.sleep(10.0)
        return httpx.Response(200, content=b"never")

    client = SupertoneClient(
        api_key="k",
        first_chunk_timeout_seconds=0.1,
        transport=httpx.MockTransport(slow_handler),
    )
    try:
        with pytest.raises(TTSFirstChunkTimeout):
            async for _ in client.synthesize_stream(
                _text_stream("느린 응답을 기다리는 문장."),
                voice_id="v1",
            ):
                pass
    finally:
        await client.aclose()


# ----------------------------------------------------------------------
# AC #3 — 429 backoff + breach budget
# ----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_429_backoff_eventually_succeeds_within_budget() -> None:
    """429 followed by 200 within budget → success (no exception)."""
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(429, content=b"rate limited")
        return httpx.Response(200, content=b"ok")

    client = SupertoneClient(
        api_key="k",
        backoff_breach_seconds=8.0,
        transport=_mock_transport(handler),
    )
    try:
        chunks: list[AudioChunk] = []
        async for chunk in client.synthesize_stream(
            _text_stream("리트라이 될 문장."),
            voice_id="v1",
        ):
            chunks.append(chunk)
    finally:
        await client.aclose()

    assert calls == 2
    assert chunks[0].data == b"ok"


@pytest.mark.asyncio
async def test_429_breach_over_budget_raises_fallthrough_signal() -> None:
    """AC #3: cumulative 429 > breach budget → TTSFallthroughSignal.

    We exploit ``monotonic`` time + a tiny budget (0s) so the second
    429 immediately breaches and we get the exception without burning
    real wall-clock in CI.
    """

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, content=b"rate limited")

    client = SupertoneClient(
        api_key="k",
        # 0s breach window — *any* sustained 429 trips the fallthrough.
        backoff_breach_seconds=0.0,
        transport=_mock_transport(handler),
    )
    try:
        with pytest.raises(TTSFallthroughSignal):
            async for _ in client.synthesize_stream(
                _text_stream("계속 429를 받는 문장."),
                voice_id="v1",
            ):
                pass
    finally:
        await client.aclose()


# ----------------------------------------------------------------------
# Misc — request-time api_key requirement
# ----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_missing_api_key_raises_at_request_time(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Construction MUST NOT fail without an api key.

    The error surfaces only when ``synthesize_stream`` is consumed —
    so the app can boot under TTS_PROVIDER=supertone without ISSUE-036
    provisioning. Tests that never call the client (e.g. import-only
    tests) must not be affected.
    """
    monkeypatch.delenv("SUPERTONE_API_KEY", raising=False)
    client = SupertoneClient()  # construction succeeds
    try:
        with pytest.raises(RuntimeError, match="ISSUE-036"):
            async for _ in client.synthesize_stream(
                _text_stream("키 없는 호출."),
                voice_id="v1",
            ):
                pass
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_api_key_picked_up_from_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``SUPERTONE_API_KEY`` env MUST be honoured at request time."""
    sent_auth: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        sent_auth.append(request.headers.get("Authorization", ""))
        return httpx.Response(200, content=b"ok")

    monkeypatch.setenv("SUPERTONE_API_KEY", "env-supplied-key")
    client = SupertoneClient(transport=_mock_transport(handler))
    try:
        async for _ in client.synthesize_stream(
            _text_stream("환경변수 키 사용 문장."),
            voice_id="v1",
        ):
            pass
    finally:
        await client.aclose()

    assert sent_auth == ["Bearer env-supplied-key"]


# ----------------------------------------------------------------------
# Buffer flush — trailing unterminated fragment
# ----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_trailing_unterminated_fragment_is_flushed() -> None:
    """A buffer with no closing terminator MUST still produce a chunk."""
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, content=f"a-{calls}".encode())

    client = SupertoneClient(
        api_key="k",
        transport=_mock_transport(handler),
    )
    try:
        chunks: list[AudioChunk] = []
        async for chunk in client.synthesize_stream(
            _text_stream("종료 마침표 없는 문장"),
            voice_id="v1",
        ):
            chunks.append(chunk)
    finally:
        await client.aclose()

    assert len(chunks) == 1
    assert chunks[0].sentence == "종료 마침표 없는 문장"
