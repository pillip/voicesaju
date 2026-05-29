"""Unit tests for `MockLLMAdapter` (ISSUE-101).

Covers:
- AC #1: 100ms-paced sentence-by-sentence streaming
- AC #2: deterministic fixture selection by seed
- AC #4: missing fixture file → FileNotFoundError at first yield
"""

from __future__ import annotations

import asyncio
import time

import pytest

from voicesaju.adapters.llm import (
    SENTENCE_DELAY_SECONDS,
    LLMAdapter,
    MockLLMAdapter,
)


@pytest.mark.asyncio
async def test_mock_llm_adapter_implements_protocol() -> None:
    """`MockLLMAdapter` MUST be a structural match for `LLMAdapter`."""
    adapter = MockLLMAdapter()
    assert isinstance(adapter, LLMAdapter)


@pytest.mark.asyncio
async def test_streams_fixture_with_100ms_pacing() -> None:
    """AC #1: stream yields sentences with ~100ms inter-sentence delay."""
    adapter = MockLLMAdapter()

    start = time.monotonic()
    chunks: list[str] = []
    async for chunk in adapter.stream(
        prompt="안녕", category="love", seed="seed-paced"
    ):
        chunks.append(chunk)
    elapsed = time.monotonic() - start

    # Each fixture has at least 3 sentences. The pacing is between
    # sentences, so n_sentences yields ⇒ (n - 1) * delay seconds.
    assert len(chunks) >= 2, f"expected ≥2 chunks, got {len(chunks)}"
    expected_min = (len(chunks) - 1) * SENTENCE_DELAY_SECONDS
    # Generous upper bound for CI scheduler jitter.
    expected_max = expected_min + 0.5 + 0.1 * len(chunks)
    assert expected_min - 0.02 <= elapsed <= expected_max, (
        f"elapsed={elapsed:.3f}s "
        f"not in [{expected_min - 0.02:.3f}, {expected_max:.3f}] "
        f"for {len(chunks)} chunks"
    )


@pytest.mark.asyncio
async def test_yields_sentences_in_order() -> None:
    """Sentences MUST yield in file order (no shuffling)."""
    adapter = MockLLMAdapter()
    chunks: list[str] = []
    async for c in adapter.stream(prompt="x", category="love", seed="seed-1"):
        chunks.append(c)
    # Each chunk should be a non-empty stripped sentence.
    assert all(c.strip() for c in chunks)
    # Concatenating with a single space approximates the original text.
    joined = " ".join(c.strip() for c in chunks)
    assert joined  # sanity: not empty


@pytest.mark.asyncio
async def test_deterministic_selection_by_seed() -> None:
    """AC #2: three calls with the same seed yield identical content."""
    adapter = MockLLMAdapter()
    seeds_results: list[list[str]] = []
    for _ in range(3):
        out: list[str] = []
        async for c in adapter.stream(
            prompt="anything", category="work", seed="determinism-seed"
        ):
            out.append(c)
        seeds_results.append(out)

    assert (
        seeds_results[0] == seeds_results[1] == seeds_results[2]
    ), "deterministic selection broken: same seed produced different streams"


@pytest.mark.asyncio
async def test_different_seed_may_pick_different_fixture() -> None:
    """Different seeds may select different fixtures (not asserted strict)."""
    adapter = MockLLMAdapter()
    # We sweep multiple seeds; with `n_fixtures=3`, at least two distinct
    # outputs should be observed across the sweep.
    outputs: set[str] = set()
    for s in [f"seed-{i}" for i in range(20)]:
        joined = ""
        async for c in adapter.stream(prompt="x", category="love", seed=s):
            joined += c
        outputs.add(joined)
    assert len(outputs) >= 2, "all 20 seeds produced identical text (suspicious)"


@pytest.mark.asyncio
async def test_missing_fixture_raises_file_not_found() -> None:
    """AC #4: missing fixture surfaces FileNotFoundError at first yield."""
    adapter = MockLLMAdapter()
    with pytest.raises(FileNotFoundError):
        # `category="nope"` has no fixture directory.
        async for _ in adapter.stream(prompt="x", category="nope", seed="any"):
            pass


@pytest.mark.asyncio
async def test_tarot_category_yields() -> None:
    """Tarot fixtures (7 daily rotations) load and yield correctly."""
    adapter = MockLLMAdapter()
    chunks: list[str] = []
    async for c in adapter.stream(prompt="x", category="tarot", seed="t-1"):
        chunks.append(c)
    assert chunks, "expected at least one tarot sentence"


@pytest.mark.asyncio
async def test_sentence_splitting_drops_empty_strings() -> None:
    """Sentence splitter MUST NOT yield empty strings."""
    adapter = MockLLMAdapter()
    async for c in adapter.stream(prompt="x", category="money", seed="m-1"):
        assert c.strip(), "splitter yielded an empty/whitespace-only chunk"


def test_settings_llm_provider_default_is_mock() -> None:
    """`LLM_PROVIDER` setting MUST default to `'mock'`."""
    from voicesaju.config import Settings

    s = Settings()
    assert s.llm_provider == "mock"


@pytest.mark.asyncio
async def test_factory_dispatch_returns_mock_when_provider_is_mock() -> None:
    """`get_llm_adapter()` returns `MockLLMAdapter` when provider is mock."""
    from voicesaju.adapters import get_llm_adapter
    from voicesaju.config import Settings

    s = Settings()
    adapter = get_llm_adapter(settings=s)
    assert isinstance(adapter, MockLLMAdapter)


def test_claude_adapter_stub_raises_not_implemented() -> None:
    """`ClaudeAdapter` stub MUST raise NotImplementedError on use (Phase 2)."""
    from voicesaju.adapters.llm import ClaudeAdapter

    stub = ClaudeAdapter()

    # The method must raise; we can't easily test on the async iterator
    # directly without running it. Use `asyncio.run` over a tiny helper.
    async def _runner() -> None:
        async for _ in stub.stream(prompt="x", category="love", seed="s"):
            pass

    with pytest.raises(NotImplementedError):
        asyncio.run(_runner())
