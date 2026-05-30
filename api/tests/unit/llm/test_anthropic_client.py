"""ISSUE-034 — Anthropic client retries, timeout, error mapping.

Tests Acceptance Criteria:
- #3: 5xx → client retries up to 2× with exponential backoff.
- #4: > 10s → ``LLMTimeoutError`` raised.

Plus the broader contract from Architecture §7:
- Successful call records a CostRecord on the supplied tracker.
- Non-5xx errors (4xx) are NOT retried — they propagate immediately as
  ``LLMClientError``.

All tests mock `anthropic.AsyncAnthropic` so no real HTTP is issued.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Any
from unittest.mock import MagicMock

import pytest

from voicesaju.llm.anthropic_client import (
    AnthropicLLMClient,
    LLMClientError,
    LLMTimeoutError,
)
from voicesaju.llm.cost_tracker import CostTracker
from voicesaju.llm.router import HAIKU_4_5, SONNET_4_6

# ---------------------------------------------------------------------------
# Fake SDK objects
# ---------------------------------------------------------------------------


class _FakeUsage:
    """Mimics `anthropic.types.Usage` (input_tokens / output_tokens fields)."""

    def __init__(self, *, input_tokens: int, output_tokens: int) -> None:
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens


class _FakeFinalMessage:
    """Mimics the value returned by `AsyncMessageStream.get_final_message()`."""

    def __init__(self, *, input_tokens: int, output_tokens: int) -> None:
        self.usage = _FakeUsage(input_tokens=input_tokens, output_tokens=output_tokens)


class _FakeAsyncStream:
    """Async context manager mirroring `AsyncMessageStream`.

    Exposes `text_stream` (async iterator of token strings) and
    `get_final_message()` (returns usage). Both are what the production
    client iterates over.
    """

    def __init__(
        self,
        *,
        tokens: list[str],
        input_tokens: int = 100,
        output_tokens: int = 200,
        per_token_delay: float = 0.0,
    ) -> None:
        self._tokens = tokens
        self._input_tokens = input_tokens
        self._output_tokens = output_tokens
        self._per_token_delay = per_token_delay

    async def __aenter__(self) -> _FakeAsyncStream:
        return self

    async def __aexit__(
        self, exc_type: Any, exc: Any, tb: Any
    ) -> None:  # pragma: no cover
        return None

    @property
    def text_stream(self) -> AsyncIterator[str]:
        return self._iter_tokens()

    async def _iter_tokens(self) -> AsyncIterator[str]:
        for token in self._tokens:
            if self._per_token_delay:
                await asyncio.sleep(self._per_token_delay)
            yield token

    async def get_final_message(self) -> _FakeFinalMessage:
        return _FakeFinalMessage(
            input_tokens=self._input_tokens,
            output_tokens=self._output_tokens,
        )


def _make_5xx_error(status: int = 503) -> Exception:
    """Build a fake `APIStatusError` with the given status code.

    The real `anthropic.APIStatusError` has a `status_code` attribute the
    retry decorator inspects. The cheapest way to mimic it without
    constructing a real httpx.Response is to subclass `Exception` and
    attach the attribute the client uses.
    """
    from anthropic import APIStatusError

    # `APIStatusError` requires a Response in some SDK versions but accepts
    # a bare instantiation via __new__ for testing. Easier: wrap in our own
    # exception that the client's retry-predicate recognises.
    response = MagicMock()
    response.status_code = status
    response.headers = {}
    err = APIStatusError.__new__(APIStatusError)
    err.message = f"simulated {status}"
    err.status_code = status
    err.response = response
    err.body = None
    err.request_id = None
    return err


# ---------------------------------------------------------------------------
# AC #1 — happy path streams tokens + records cost
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_stream_yields_tokens_and_records_cost() -> None:
    """Successful stream yields each token and writes a CostRecord."""
    tracker = CostTracker()
    fake_stream = _FakeAsyncStream(
        tokens=["안녕", "하세요", "."],
        input_tokens=150,
        output_tokens=3,
    )

    fake_messages = MagicMock()
    fake_messages.stream = MagicMock(return_value=fake_stream)

    fake_sdk = MagicMock()
    fake_sdk.messages = fake_messages

    client = AnthropicLLMClient(
        api_key="dummy",
        cost_tracker=tracker,
        sdk_client=fake_sdk,
        input_krw_per_mtok={SONNET_4_6: 4_000.0, HAIKU_4_5: 1_000.0},
        output_krw_per_mtok={SONNET_4_6: 20_000.0, HAIKU_4_5: 5_000.0},
    )

    collected: list[str] = []
    async for tok in client.stream(
        model=SONNET_4_6,
        system="sys",
        user="hello",
        max_tokens=128,
    ):
        collected.append(tok)

    assert collected == ["안녕", "하세요", "."]
    assert len(tracker.records) == 1
    rec = tracker.records[0]
    assert rec.model == SONNET_4_6
    assert rec.input_tokens == 150
    assert rec.output_tokens == 3
    assert rec.total_krw > 0


# ---------------------------------------------------------------------------
# AC #3 — 5xx retry up to 2× with backoff
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_stream_retries_on_5xx_twice_then_succeeds() -> None:
    """Two 503s, then success — retry budget MUST be enough to recover."""
    tracker = CostTracker()

    success_stream = _FakeAsyncStream(
        tokens=["ok"],
        input_tokens=10,
        output_tokens=1,
    )

    # `messages.stream(...)` returns the stream-or-raises object. We make
    # it raise twice (simulating the SDK surfacing a 503 from the API)
    # then return the success stream on the 3rd attempt.
    call_count = {"n": 0}

    def _stream_factory(*args: Any, **kwargs: Any) -> Any:
        call_count["n"] += 1
        if call_count["n"] <= 2:
            raise _make_5xx_error(503)
        return success_stream

    fake_messages = MagicMock()
    fake_messages.stream = MagicMock(side_effect=_stream_factory)

    fake_sdk = MagicMock()
    fake_sdk.messages = fake_messages

    client = AnthropicLLMClient(
        api_key="dummy",
        cost_tracker=tracker,
        sdk_client=fake_sdk,
        # Speed up backoff so the test runs in <1s.
        retry_initial_delay=0.001,
        retry_max_delay=0.005,
    )

    collected: list[str] = []
    async for tok in client.stream(
        model=HAIKU_4_5,
        system="sys",
        user="hello",
        max_tokens=32,
    ):
        collected.append(tok)

    assert collected == ["ok"]
    # 2 failures + 1 success = 3 total stream calls (max 2 retries).
    assert call_count["n"] == 3
    # Cost recorded for the successful attempt only.
    assert len(tracker.records) == 1


@pytest.mark.asyncio
async def test_stream_gives_up_after_two_retries() -> None:
    """3 consecutive 503s → propagate as LLMClientError (no infinite retry)."""
    tracker = CostTracker()
    call_count = {"n": 0}

    def _always_fails(*args: Any, **kwargs: Any) -> Any:
        call_count["n"] += 1
        raise _make_5xx_error(503)

    fake_messages = MagicMock()
    fake_messages.stream = MagicMock(side_effect=_always_fails)

    fake_sdk = MagicMock()
    fake_sdk.messages = fake_messages

    client = AnthropicLLMClient(
        api_key="dummy",
        cost_tracker=tracker,
        sdk_client=fake_sdk,
        retry_initial_delay=0.001,
        retry_max_delay=0.005,
    )

    with pytest.raises(LLMClientError):
        async for _ in client.stream(
            model=HAIKU_4_5,
            system="sys",
            user="hello",
            max_tokens=32,
        ):
            pass  # pragma: no cover

    # Initial attempt + 2 retries = 3 calls. Anything higher would mean
    # the budget is unbounded.
    assert call_count["n"] == 3
    assert tracker.records == []


@pytest.mark.asyncio
async def test_stream_does_not_retry_on_4xx() -> None:
    """4xx (e.g. 401/400) is a client bug — retrying just wastes quota."""
    tracker = CostTracker()
    call_count = {"n": 0}

    def _client_error(*args: Any, **kwargs: Any) -> Any:
        call_count["n"] += 1
        raise _make_5xx_error(401)  # status doesn't have to be 5xx here

    fake_messages = MagicMock()
    fake_messages.stream = MagicMock(side_effect=_client_error)

    fake_sdk = MagicMock()
    fake_sdk.messages = fake_messages

    client = AnthropicLLMClient(
        api_key="dummy",
        cost_tracker=tracker,
        sdk_client=fake_sdk,
        retry_initial_delay=0.001,
        retry_max_delay=0.005,
    )

    with pytest.raises(LLMClientError):
        async for _ in client.stream(
            model=HAIKU_4_5,
            system="sys",
            user="hello",
            max_tokens=32,
        ):
            pass  # pragma: no cover

    # Exactly 1 attempt — no retry on 4xx.
    assert call_count["n"] == 1


# ---------------------------------------------------------------------------
# AC #4 — timeout
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_stream_raises_llm_timeout_on_slow_stream() -> None:
    """A stream that yields a token every 5s exceeds the 10s budget.

    We patch `asyncio.timeout` would be invasive — instead the client
    accepts a `timeout_seconds` ctor arg. We set it tiny (0.05s) and
    make the stream sleep longer than that per token, then assert the
    `LLMTimeoutError` surfaces with no partial cost recorded.
    """
    tracker = CostTracker()
    slow_stream = _FakeAsyncStream(
        tokens=["하나", "둘", "셋"],
        per_token_delay=0.5,
        input_tokens=100,
        output_tokens=10,
    )

    fake_messages = MagicMock()
    fake_messages.stream = MagicMock(return_value=slow_stream)
    fake_sdk = MagicMock()
    fake_sdk.messages = fake_messages

    client = AnthropicLLMClient(
        api_key="dummy",
        cost_tracker=tracker,
        sdk_client=fake_sdk,
        timeout_seconds=0.05,
        retry_initial_delay=0.001,
        retry_max_delay=0.005,
        # Timeouts must NOT be retried — they almost always indicate the
        # whole call is unresponsive, not a transient hiccup.
    )

    with pytest.raises(LLMTimeoutError):
        async for _ in client.stream(
            model=SONNET_4_6,
            system="sys",
            user="hello",
            max_tokens=32,
        ):
            pass  # pragma: no cover

    # Cost MUST NOT be recorded for a timed-out (incomplete) call. The
    # billing model accepts under-counting (some real tokens were used)
    # over over-counting (which would double-charge on retry from
    # caller).
    assert tracker.records == []


# ---------------------------------------------------------------------------
# Configuration smoke tests
# ---------------------------------------------------------------------------


class TestClientConstruction:
    def test_requires_api_key(self) -> None:
        """Empty / None API key fails fast — better than a 401 surprise."""
        with pytest.raises((ValueError, TypeError)):
            AnthropicLLMClient(api_key="", cost_tracker=CostTracker())

    def test_accepts_injected_sdk(self) -> None:
        """Sanity: injection works so unit tests can avoid real SDK."""
        sentinel = MagicMock()
        client = AnthropicLLMClient(
            api_key="dummy",
            cost_tracker=CostTracker(),
            sdk_client=sentinel,
        )
        assert client._sdk is sentinel
