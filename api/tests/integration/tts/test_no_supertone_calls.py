"""ISSUE-102 AC #3 — zero outbound HTTP to Supertone under TTS_PROVIDER=mock.

Marked as `integration` so it stays out of the default suite; CI invokes
the integration marker explicitly when network-block tests are needed.

We do NOT depend on the optional `responses` lib here. Instead we patch
`socket.getaddrinfo` to fail loudly on Supertone host lookups — that
single hook covers httpx, requests, aiohttp, and anything else that
ultimately resolves a hostname. Mirrors the ISSUE-101 pattern.
"""

from __future__ import annotations

import socket
from unittest.mock import patch

import pytest

from voicesaju.adapters.tts import MockTTSAdapter

_BLOCKED_HOSTS = (
    "api.supertone.ai",
    "supertone.ai",
    "supertoneinc.com",
)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_mock_tts_makes_zero_supertone_calls() -> None:
    """Streaming the mock TTS adapter MUST NOT resolve any Supertone host."""
    real_getaddrinfo = socket.getaddrinfo
    seen: list[str] = []

    def _guard(host, *args, **kwargs):  # type: ignore[no-untyped-def]
        seen.append(host)
        host_lower = host.lower() if isinstance(host, str) else ""
        if any(host_lower.endswith(blocked) for blocked in _BLOCKED_HOSTS):
            raise AssertionError(f"BANNED: mock TTS adapter attempted DNS to {host}")
        return real_getaddrinfo(host, *args, **kwargs)

    with patch("socket.getaddrinfo", side_effect=_guard):
        adapter = MockTTSAdapter()
        async for _ in adapter.stream(text="안녕", voice_id="nuna"):
            pass

    # Sanity: assertion above doesn't trigger on legitimate non-Supertone
    # hosts (none expected in this hermetic path anyway).
    assert all(
        not (isinstance(host, str) and host.lower().endswith(blocked))
        for host in seen
        for blocked in _BLOCKED_HOSTS
    )
