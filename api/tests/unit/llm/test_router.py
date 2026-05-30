"""ISSUE-034 — Router selects Sonnet 4.6 vs Haiku 4.5 per task kind.

Tests Acceptance Criteria #1 + #2:
- `stream_saju_main` → Sonnet 4.6.
- `stream_followup` → Haiku 4.5.

Plus the broader routing surface defined in Architecture §7.1:
- `stream_tarot` → Haiku.
- `generate_followup_questions` → Haiku (non-streaming).
- `extract_quote` → Haiku (non-streaming).

The router is implemented as a **pure function**: `select_model(task_kind) -> str`.
No I/O, no async — that way every call site can be reasoned about in
isolation, and integration with `anthropic_client` is just plumbing.
"""

from __future__ import annotations

import pytest

from voicesaju.llm.router import (
    HAIKU_4_5,
    SONNET_4_6,
    TaskKind,
    select_model,
)


class TestSelectModel:
    """Pure model-routing decisions per Architecture §7.1."""

    def test_main_saju_uses_sonnet_4_6(self) -> None:
        """AC #1: main saju reading routes to Sonnet 4.6."""
        assert select_model(TaskKind.SAJU_MAIN) == SONNET_4_6

    def test_followup_answer_uses_haiku_4_5(self) -> None:
        """AC #2: follow-up answer routes to Haiku 4.5."""
        assert select_model(TaskKind.FOLLOWUP_ANSWER) == HAIKU_4_5

    def test_tarot_uses_haiku_4_5(self) -> None:
        """Architecture §7.1: tarot uses Haiku to stay under cost ceiling."""
        assert select_model(TaskKind.TAROT) == HAIKU_4_5

    def test_followup_question_suggest_uses_haiku_4_5(self) -> None:
        """Architecture §7.1: follow-up Q suggestion is Haiku JSON mode."""
        assert select_model(TaskKind.FOLLOWUP_SUGGEST) == HAIKU_4_5

    def test_quote_extraction_uses_haiku_4_5(self) -> None:
        """Architecture §7.1: quote extraction is one-shot Haiku."""
        assert select_model(TaskKind.QUOTE_EXTRACT) == HAIKU_4_5

    def test_model_ids_are_strings(self) -> None:
        """Defence in depth — IDs must be plain str for SDK consumption."""
        assert isinstance(SONNET_4_6, str)
        assert isinstance(HAIKU_4_5, str)
        # Neither ID is empty (regression: a None default would silently
        # break the SDK with a 400).
        assert SONNET_4_6
        assert HAIKU_4_5

    def test_sonnet_and_haiku_differ(self) -> None:
        """Routing must distinguish the two models; identical IDs would
        collapse the whole §7.1 cost-routing argument."""
        assert SONNET_4_6 != HAIKU_4_5


class TestTaskKindEnum:
    """The TaskKind enum is the public surface — adding a value MUST be a
    conscious decision (NFR-007 cost ceiling assumes a known set)."""

    def test_known_task_kinds(self) -> None:
        # If a value is added/removed, this test forces an update so
        # `cost_tracker`'s per-kind aggregates stay in sync.
        expected = {
            "SAJU_MAIN",
            "FOLLOWUP_SUGGEST",
            "FOLLOWUP_ANSWER",
            "TAROT",
            "QUOTE_EXTRACT",
        }
        assert {k.name for k in TaskKind} == expected


class TestUnknownTaskKindRaises:
    """Bad input should fail loudly (not silently default to Sonnet — that
    would be a cost-ceiling violation)."""

    def test_unknown_string_raises(self) -> None:
        with pytest.raises((KeyError, ValueError)):
            select_model("not_a_task_kind")  # type: ignore[arg-type]
