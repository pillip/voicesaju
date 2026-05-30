"""End-to-end mocked Supertone streaming test (ISSUE-037).

Marked as ``integration`` so it stays out of the default suite — CI
invokes the integration marker explicitly. We use ``httpx.MockTransport``
to mimic a Supertone response burst across multiple sentences.

What it exercises:
- ``synthesize_stream`` (module-level convenience) wires up an
  in-process client end-to-end.
- Multiple sentences in one upstream LLM-stream fragment produce
  ordered ``AudioChunk`` objects.
- The api-key requirement is satisfied via env (mirrors the real
  production path).
- ``zero outbound HTTP`` invariant from ISSUE-102 still holds — we
  reuse the ``api.supertone.ai`` host guard.
"""

from __future__ import annotations

import socket
from collections.abc import AsyncIterator
from unittest.mock import patch

import httpx
import pytest

from voicesaju.tts.supertone_client import AudioChunk, synthesize_stream

_BLOCKED_HOSTS = (
    "api.supertone.ai",
    "supertone.ai",
    "supertoneinc.com",
)


async def _llm_like_stream() -> AsyncIterator[str]:
    """Mimic an LLM SSE stream: text arrives in arbitrary fragment boundaries."""
    yield "오늘의 사주는 "
    yield "전반적으로 좋아요. "
    yield "특히 오후"
    yield "에 좋은 일이 생겨요!"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_end_to_end_mocked_supertone_stream(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Full streaming round-trip against a mocked Supertone transport.

    Sentences should arrive in source order with all four AudioChunk
    fields populated (data, seq, sentence, voice_id). The mocked
    transport returns deterministic bytes per request so we can
    assert exact payloads.
    """
    request_payloads: list[dict[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        import json as _json

        payload = _json.loads(request.content)
        request_payloads.append(payload)
        # Return a deterministic per-sentence audio payload so the
        # assertion can pin to bytes.
        return httpx.Response(
            200,
            content=f"AUDIO[{payload['text']}]".encode(),
        )

    monkeypatch.setenv("SUPERTONE_API_KEY", "integration-test-key")

    chunks: list[AudioChunk] = []
    async for chunk in synthesize_stream(
        _llm_like_stream(),
        voice_id="voice_id_nuna_v1",
        transport=httpx.MockTransport(handler),
    ):
        chunks.append(chunk)

    # The LLM-like stream contains exactly 2 sentence terminators (.
    # twice) plus a trailing ``!`` for a total of 3 sentences.
    sentences_emitted = [c.sentence for c in chunks]
    assert sentences_emitted == [
        "오늘의 사주는 전반적으로 좋아요.",
        "특히 오후에 좋은 일이 생겨요!",
    ]
    # seq is monotonic from 0.
    assert [c.seq for c in chunks] == list(range(len(chunks)))
    # voice_id is echoed on every chunk.
    assert all(c.voice_id == "voice_id_nuna_v1" for c in chunks)
    # Payload bytes match the mocked echo.
    assert [c.data for c in chunks] == [
        b"AUDIO[\xec\x98\xa4\xeb\x8a\x98\xec\x9d\x98 \xec\x82\xac\xec\xa3"
        b"\xbc\xeb\x8a\x94 \xec\xa0\x84\xeb\xb0\x98\xec\xa0\x81\xec\x9c\xbc"
        b"\xeb\xa1\x9c \xec\xa2\x8b\xec\x95\x84\xec\x9a\x94.]",
        b"AUDIO[\xed\x8a\xb9\xed\x9e\x88 \xec\x98\xa4\xed\x9b\x84\xec\x97\x90"
        b" \xec\xa2\x8b\xec\x9d\x80 \xec\x9d\xbc\xec\x9d\xb4 \xec\x83\x9d"
        b"\xea\xb2\xa8\xec\x9a\x94!]",
    ]
    # Each sentence is sent verbatim in the request body.
    assert [p["text"] for p in request_payloads] == sentences_emitted
    assert all(p["voice_id"] == "voice_id_nuna_v1" for p in request_payloads)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_mocked_stream_makes_zero_supertone_dns_lookups(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Mirrors ISSUE-102's network-block invariant for the structural client.

    Even when ``TTS_PROVIDER`` is wired to use the structural Supertone
    client, the mocked transport MUST NOT resolve any Supertone host.
    """
    real_getaddrinfo = socket.getaddrinfo
    seen: list[str] = []

    def _guard(host, *args, **kwargs):  # type: ignore[no-untyped-def]
        seen.append(host)
        host_lower = host.lower() if isinstance(host, str) else ""
        if any(host_lower.endswith(blocked) for blocked in _BLOCKED_HOSTS):
            raise AssertionError(
                f"BANNED: mocked Supertone client attempted DNS to {host}"
            )
        return real_getaddrinfo(host, *args, **kwargs)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"\xff\xfb\x00\x00")

    monkeypatch.setenv("SUPERTONE_API_KEY", "k")
    with patch("socket.getaddrinfo", side_effect=_guard):
        async for _ in synthesize_stream(
            _llm_like_stream(),
            voice_id="voice_id_nuna_v1",
            transport=httpx.MockTransport(handler),
        ):
            pass

    assert all(
        not (isinstance(host, str) and host.lower().endswith(blocked))
        for host in seen
        for blocked in _BLOCKED_HOSTS
    )
