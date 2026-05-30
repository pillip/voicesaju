"""ISSUE-034 — Integration: streaming saju main end-to-end with mock SDK.

Marked `integration` so it stays out of the default unit suite — it
exercises the router → anthropic_client → cost_tracker layering against
a fake Anthropic SDK plus the ClaudeAdapter shim from
`voicesaju.adapters.llm` (with `LLM_PROVIDER=claude`).

We deliberately do NOT call `respx` here: the anthropic SDK builds its
own httpx client internally, so mocking at the HTTPX layer would require
constructing valid Anthropic SSE bodies. Mocking the SDK object directly
is much more robust and is also what the unit tests do.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any
from unittest.mock import MagicMock

import pytest

from voicesaju.llm.anthropic_client import AnthropicLLMClient
from voicesaju.llm.cost_tracker import CostTracker
from voicesaju.llm.router import HAIKU_4_5, SONNET_4_6, TaskKind, select_model


class _FakeUsage:
    def __init__(self, *, input_tokens: int, output_tokens: int) -> None:
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens


class _FakeFinalMessage:
    def __init__(self, *, input_tokens: int, output_tokens: int) -> None:
        self.usage = _FakeUsage(input_tokens=input_tokens, output_tokens=output_tokens)


class _FakeAsyncStream:
    """End-to-end fake — mimics `AsyncMessageStream`."""

    def __init__(
        self,
        *,
        tokens: list[str],
        input_tokens: int = 200,
        output_tokens: int = 50,
    ) -> None:
        self._tokens = tokens
        self._input_tokens = input_tokens
        self._output_tokens = output_tokens

    async def __aenter__(self) -> _FakeAsyncStream:
        return self

    async def __aexit__(
        self, exc_type: Any, exc: Any, tb: Any
    ) -> None:  # pragma: no cover
        return None

    @property
    def text_stream(self) -> AsyncIterator[str]:
        return self._iter()

    async def _iter(self) -> AsyncIterator[str]:
        for tok in self._tokens:
            yield tok

    async def get_final_message(self) -> _FakeFinalMessage:
        return _FakeFinalMessage(
            input_tokens=self._input_tokens,
            output_tokens=self._output_tokens,
        )


def _build_client(tracker: CostTracker) -> AnthropicLLMClient:
    """Construct a client wired to a fake SDK that returns predictable
    tokens for both Sonnet and Haiku calls."""

    def _stream_factory(*args: Any, **kwargs: Any) -> _FakeAsyncStream:
        model = kwargs.get("model", "")
        # Tag the tokens by the model so we can assert routing E2E.
        if model == SONNET_4_6:
            return _FakeAsyncStream(
                tokens=["S1 ", "S2 ", "S3"],
                input_tokens=1_500,
                output_tokens=1_200,
            )
        else:
            return _FakeAsyncStream(
                tokens=["H1 ", "H2"],
                input_tokens=800,
                output_tokens=450,
            )

    fake_messages = MagicMock()
    fake_messages.stream = MagicMock(side_effect=_stream_factory)
    fake_sdk = MagicMock()
    fake_sdk.messages = fake_messages

    return AnthropicLLMClient(
        api_key="dummy",
        cost_tracker=tracker,
        sdk_client=fake_sdk,
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_stream_saju_main_routes_sonnet_and_records_cost() -> None:
    """Main saju reading → Sonnet 4.6, cost recorded with Sonnet pricing."""
    tracker = CostTracker()
    client = _build_client(tracker)

    # Caller-level helper: pick the model via the router, then stream.
    model = select_model(TaskKind.SAJU_MAIN)
    assert model == SONNET_4_6

    collected: list[str] = []
    async for tok in client.stream(
        model=model,
        system="character_block + task_block + determinism_block + output_block",
        user="<saju_chart_json>\n카테고리: 연애",
        max_tokens=2048,
    ):
        collected.append(tok)

    assert "".join(collected) == "S1 S2 S3"
    assert len(tracker.records) == 1
    rec = tracker.records[0]
    assert rec.model == SONNET_4_6
    assert rec.input_tokens == 1_500
    assert rec.output_tokens == 1_200
    # Sonnet pricing > 0 → KRW positive (exact rates are config-driven).
    assert rec.total_krw > 0


@pytest.mark.integration
@pytest.mark.asyncio
async def test_stream_followup_routes_haiku_and_records_cost() -> None:
    """Follow-up answer → Haiku 4.5, separate CostRecord."""
    tracker = CostTracker()
    client = _build_client(tracker)

    model = select_model(TaskKind.FOLLOWUP_ANSWER)
    assert model == HAIKU_4_5

    collected: list[str] = []
    async for tok in client.stream(
        model=model,
        system="character + followup_task",
        user="질문: 다음 달은 어떤가요? <prior_summary>",
        max_tokens=512,
    ):
        collected.append(tok)

    assert "".join(collected) == "H1 H2"
    assert len(tracker.records) == 1
    assert tracker.records[0].model == HAIKU_4_5


@pytest.mark.integration
@pytest.mark.asyncio
async def test_full_reading_session_aggregates_cost() -> None:
    """One Sonnet main + one Haiku follow-up → two records, aggregated."""
    tracker = CostTracker()
    client = _build_client(tracker)

    # Main reading.
    async for _ in client.stream(
        model=SONNET_4_6, system="s", user="u", max_tokens=2048
    ):
        pass

    # Follow-up.
    async for _ in client.stream(model=HAIKU_4_5, system="s", user="u", max_tokens=512):
        pass

    assert len(tracker.records) == 2
    # Aggregate must be the sum of both per-call KRW totals.
    assert tracker.total_krw() == pytest.approx(
        tracker.records[0].total_krw + tracker.records[1].total_krw
    )
    # Token totals also aggregate.
    assert tracker.total_input_tokens() == 1_500 + 800
    assert tracker.total_output_tokens() == 1_200 + 450
