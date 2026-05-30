"""LLM adapter Protocol + Phase 1 mock implementation (ISSUE-101).

Phase 1 ships `MockLLMAdapter` which streams pre-authored fixture text
sentence-by-sentence with a 100ms inter-sentence delay so downstream
pipelines (chunked audio player in ISSUE-033, SSE pipeline in ISSUE-039)
exercise the same timing-sensitive paths they will under the real
Anthropic SSE client.

`ClaudeAdapter` is a Phase 2 stub — instantiating succeeds so the app
boots under `LLM_PROVIDER=claude`, but calling `stream()` raises
``NotImplementedError`` pointing at ISSUE-035.

PRD-Ref: FR-008 (saju reading), FR-009 (daily tarot).
"""

from __future__ import annotations

import asyncio
import hashlib
import re
from collections.abc import AsyncIterator
from pathlib import Path
from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    # ISSUE-034: forward-only refs so the module import stays cheap and
    # `LLM_PROVIDER=mock` paths never touch the anthropic SDK.
    from voicesaju.config import Settings
    from voicesaju.llm.anthropic_client import AnthropicLLMClient
    from voicesaju.llm.cost_tracker import CostTracker

# Inter-sentence pacing. Picked to mirror the steady-state token-burst
# cadence we see from Anthropic SSE so downstream timing tests don't
# need to be re-tuned when the real adapter lands.
SENTENCE_DELAY_SECONDS: float = 0.1

# Sentence splitter — keeps the trailing punctuation with the chunk so
# the audio pipeline can use it as a prosody hint. Upgrade to a Korean-
# aware splitter if the deny-list integration test (ISSUE-020 layer)
# reveals false positives mid-sentence.
_SENTENCE_BOUNDARY_RE = re.compile(r"(?<=[.?!])\s+")


def _split_sentences(text: str) -> list[str]:
    """Split `text` on `.?!` boundaries and drop empty/whitespace chunks."""
    return [chunk for chunk in _SENTENCE_BOUNDARY_RE.split(text.strip()) if chunk]


# ---------------------------------------------------------------------------
# Protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class LLMAdapter(Protocol):
    """Provider-agnostic streaming LLM client used by reading pipelines.

    The Protocol is `runtime_checkable` so `isinstance(obj, LLMAdapter)`
    works in tests without requiring a concrete base class.
    """

    def stream(self, prompt: str, category: str, seed: str) -> AsyncIterator[str]:
        """Yield response chunks (sentences) for the given prompt.

        Implementations MUST yield non-empty chunks in order. The
        contract does NOT specify whether implementations pace yields —
        the mock does, the real Anthropic client will yield as fast as
        the SSE arrives.
        """
        ...


# ---------------------------------------------------------------------------
# MockLLMAdapter
# ---------------------------------------------------------------------------


class MockLLMAdapter:
    """Fixture-based streaming LLM for the Phase 1 PoC stack.

    Reads from ``api/tests/fixtures/llm/{category}/{n}.txt``:

    - Saju categories (`love`, `work`, `money`): 3 fixtures each.
    - Tarot: 7 fixtures, one per weekday-style rotation.

    Selection is deterministic — the same `seed` always picks the same
    fixture file via `hash(seed) % n_fixtures` so re-running a reading
    in a debugger produces stable output.
    """

    # Default base path resolves to the canonical fixtures shipped with
    # the repo. Tests that need a different layout can pass an explicit
    # `fixtures_root` for hermetic temp dirs.
    _DEFAULT_FIXTURES_ROOT: Path = (
        Path(__file__).resolve().parent.parent.parent / "tests" / "fixtures" / "llm"
    )

    def __init__(self, fixtures_root: Path | None = None) -> None:
        self._fixtures_root = fixtures_root or self._DEFAULT_FIXTURES_ROOT

    async def stream(self, prompt: str, category: str, seed: str) -> AsyncIterator[str]:
        """Stream fixture sentences with `SENTENCE_DELAY_SECONDS` pacing.

        Raises:
            FileNotFoundError: when no fixture file exists for the given
                category and computed index. The error surfaces at the
                first iteration step so callers see a clear failure
                rather than an empty stream.
        """
        fixture_path = self._pick_fixture(category=category, seed=seed)
        text = fixture_path.read_text(encoding="utf-8")
        sentences = _split_sentences(text)

        for idx, sentence in enumerate(sentences):
            if idx > 0:
                # Pacing happens between sentences only, so n sentences
                # produce exactly (n - 1) sleeps. The first chunk is
                # emitted immediately to mirror Anthropic SSE behaviour.
                await asyncio.sleep(SENTENCE_DELAY_SECONDS)
            yield sentence

    # ---- Internal helpers ----

    def _pick_fixture(self, *, category: str, seed: str) -> Path:
        """Return the deterministic fixture path for `(category, seed)`.

        Raises ``FileNotFoundError`` when the category directory has no
        fixtures (e.g. when called with an unknown category — a likely
        misconfiguration we want to surface loudly).
        """
        category_dir = self._fixtures_root / category
        if not category_dir.is_dir():
            raise FileNotFoundError(
                f"LLM fixture directory not found: {category_dir} "
                f"(category={category!r})"
            )

        # Enumerate fixtures deterministically — sorted by filename so
        # `hash(seed) % n` always lands on the same file across runs.
        fixtures = sorted(category_dir.glob("*.txt"))
        if not fixtures:
            raise FileNotFoundError(
                f"No .txt fixtures in {category_dir} (category={category!r})"
            )

        # Python's builtin `hash()` is salted per-process, so we use a
        # stable digest. Cheap, deterministic, and uniform enough for a
        # 3..7-bucket distribution.
        digest = hashlib.sha256(seed.encode("utf-8")).digest()
        idx = int.from_bytes(digest[:8], "big") % len(fixtures)
        return fixtures[idx]


# ---------------------------------------------------------------------------
# ClaudeAdapter — real Anthropic SSE wrapper (ISSUE-034)
# ---------------------------------------------------------------------------


class ClaudeAdapter:
    """LLMAdapter implementation that delegates to ``AnthropicLLMClient``.

    ISSUE-034 replaces the original Phase 2 stub with a working class.
    Instantiation succeeds even when ``ANTHROPIC_API_KEY`` is missing —
    only ``stream()`` enforces the key, so ``LLM_PROVIDER=claude`` can
    be wired in non-prod before the Phase 2 ISSUE-035 key provisioning
    is complete.

    The adapter applies the **router** here: a `category` like
    ``"saju_love"`` / ``"saju_work"`` / ``"saju_money"`` routes to the
    main-saju Sonnet path, while ``"tarot"`` / ``"followup"`` route to
    the Haiku path. The protocol's `prompt` argument is forwarded
    verbatim — composition of system + user blocks is the pipeline's
    responsibility (Architecture §7.2).
    """

    def __init__(
        self,
        *,
        settings: Settings | None = None,
        cost_tracker: CostTracker | None = None,
    ) -> None:
        # Lazy import — keeps the stub-equivalent constructor cheap and
        # avoids cyclic imports if Settings ever needs the LLM module.
        from voicesaju.config import get_settings as _get_settings
        from voicesaju.llm.cost_tracker import CostTracker as _CostTracker

        self._settings = settings or _get_settings()
        self._tracker = cost_tracker or _CostTracker()
        self._client: AnthropicLLMClient | None = None  # built lazily.

    @property
    def cost_tracker(self) -> CostTracker:
        return self._tracker

    def _ensure_client(self) -> AnthropicLLMClient:
        """Build the underlying ``AnthropicLLMClient`` on first use.

        Lazy construction so that ``LLM_PROVIDER=claude`` boots even
        without an API key (only ``stream()`` errors). The factory
        injects KRW pricing from Settings so production runs reflect
        the latest OQ-01 figures without a code change.
        """
        if self._client is not None:
            return self._client

        from voicesaju.llm.anthropic_client import AnthropicLLMClient
        from voicesaju.llm.router import HAIKU_4_5, SONNET_4_6

        api_key = self._settings.anthropic_api_key
        if not api_key:
            raise RuntimeError(
                "ANTHROPIC_API_KEY is not configured. Set it via env or "
                ".env.local before using LLM_PROVIDER=claude (see ISSUE-035)."
            )

        self._client = AnthropicLLMClient(
            api_key=api_key,
            cost_tracker=self._tracker,
            input_krw_per_mtok={
                SONNET_4_6: self._settings.anthropic_sonnet_input_krw_per_mtok,
                HAIKU_4_5: self._settings.anthropic_haiku_input_krw_per_mtok,
            },
            output_krw_per_mtok={
                SONNET_4_6: self._settings.anthropic_sonnet_output_krw_per_mtok,
                HAIKU_4_5: self._settings.anthropic_haiku_output_krw_per_mtok,
            },
        )
        return self._client

    def _route_category(self, category: str) -> str:
        """Map the legacy `category` string onto a router ``TaskKind``.

        Categories prefixed with ``saju_`` go to the main reading path
        (Sonnet). Anything else (``tarot``, ``followup_*``) routes to
        Haiku per Architecture §7.1. Unknown categories default to
        Haiku — safer (cheaper) than defaulting to Sonnet.
        """
        from voicesaju.llm.router import TaskKind, select_model

        if category.startswith("saju"):
            return select_model(TaskKind.SAJU_MAIN)
        if category.startswith("followup"):
            return select_model(TaskKind.FOLLOWUP_ANSWER)
        if category == "tarot":
            return select_model(TaskKind.TAROT)
        # Conservative default: cheaper model on an unknown category.
        return select_model(TaskKind.FOLLOWUP_ANSWER)

    async def stream(self, prompt: str, category: str, seed: str) -> AsyncIterator[str]:
        """Stream tokens from Anthropic.

        Forwards the protocol's `prompt` as the user message. `seed` is
        passed through as metadata (currently unused by the SDK call
        but reserved for traceability — `Reading.engine_version` writes
        rely on the caller knowing the seed).
        """
        # NB: imports inside `stream()` to keep top-level import cheap;
        # see ISSUE-101 ClaudeAdapter docstring for the original
        # rationale (the file is the entry point for `from voicesaju.
        # adapters.llm import …` even when only the mock is used).
        client = self._ensure_client()
        model = self._route_category(category)

        # `system` block is empty — callers compose the full system
        # prompt into `prompt` to match the legacy LLMAdapter protocol.
        # The pipeline orchestrator (ISSUE-039) will adopt the richer
        # `(system, user, max_tokens)` shape directly via
        # AnthropicLLMClient when the prompt-template machinery lands.
        async for token in client.stream(
            model=model,
            system="",
            user=prompt,
            max_tokens=2048,
        ):
            yield token


__all__ = [
    "ClaudeAdapter",
    "LLMAdapter",
    "MockLLMAdapter",
    "SENTENCE_DELAY_SECONDS",
]
