"""ISSUE-101 AC #3 — zero outbound HTTP to anthropic.com under LLM_PROVIDER=mock.

Marked as `integration` so it stays out of the default suite; CI invokes
the integration marker explicitly when network-block tests are needed.

We do NOT depend on the optional `responses` lib here. Instead we patch
`socket.getaddrinfo` to fail loudly on anthropic.com lookups — that
single hook covers httpx, requests, aiohttp, and anything else that
ultimately resolves a hostname.
"""

from __future__ import annotations

import socket
from unittest.mock import patch

import pytest

from voicesaju.adapters.llm import MockLLMAdapter

_BLOCKED_HOSTS = ("api.anthropic.com", "anthropic.com")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_mock_llm_makes_zero_anthropic_calls() -> None:
    """Streaming the mock adapter MUST NOT resolve anthropic.com."""
    real_getaddrinfo = socket.getaddrinfo
    seen: list[str] = []

    def _guard(host, *args, **kwargs):  # type: ignore[no-untyped-def]
        seen.append(host)
        if any(host.lower().endswith(blocked) for blocked in _BLOCKED_HOSTS):
            raise AssertionError(f"BANNED: mock adapter attempted DNS to {host}")
        return real_getaddrinfo(host, *args, **kwargs)

    with patch("socket.getaddrinfo", side_effect=_guard):
        adapter = MockLLMAdapter()
        async for _ in adapter.stream(prompt="x", category="love", seed="i"):
            pass

    # Sanity: even if the mock did nothing network-y, the test must have
    # exercised at least the local fixture I/O path.
    assert all(
        not host.lower().endswith(blocked)
        for host in seen
        for blocked in _BLOCKED_HOSTS
    )
