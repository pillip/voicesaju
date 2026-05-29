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
from typing import Protocol, runtime_checkable

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
# ClaudeAdapter — Phase 2 stub
# ---------------------------------------------------------------------------


class ClaudeAdapter:
    """Phase 2 real-Anthropic adapter — instantiation succeeds, calls fail.

    Importing/instantiating does NOT raise so `LLM_PROVIDER=claude` can
    be wired before the real client lands; `stream()` raises
    ``NotImplementedError`` pointing at ISSUE-035.
    """

    async def stream(self, prompt: str, category: str, seed: str) -> AsyncIterator[str]:
        raise NotImplementedError("ClaudeAdapter is a Phase 2 stub. See ISSUE-035.")
        # Unreachable but keeps mypy happy about the AsyncIterator return.
        yield ""  # pragma: no cover


__all__ = [
    "ClaudeAdapter",
    "LLMAdapter",
    "MockLLMAdapter",
    "SENTENCE_DELAY_SECONDS",
]
