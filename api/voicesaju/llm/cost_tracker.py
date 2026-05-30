"""Per-call cost accounting for the LLM layer (Architecture §7.4).

`CostTracker` is an in-memory aggregator: each call to
``anthropic_client`` appends a `CostRecord` capturing
``(model, input_tokens, output_tokens, unit_prices, total_krw)``. The
reading pipeline reads ``tracker.total_krw()`` at the end of the
session and writes it to ``Reading.cost_krw`` for the NFR-007 dashboard.

Persistence (DB write) is intentionally not in this module — the
pipeline orchestrator (ISSUE-039) owns the transaction boundary.

KRW pricing values are NOT hardcoded here. They come from
``voicesaju.config.Settings`` and are injected per call. That way:

1. Tests can use round numbers (4_000.0 / 20_000.0) for clear assertions.
2. Production can update prices via env without a code change.
3. PRD §11 OQ-01 (exact 2026 Anthropic pricing) stays a config concern,
   not a code concern.
"""

from __future__ import annotations

from dataclasses import dataclass, field


def compute_call_krw(
    *,
    input_tokens: int,
    output_tokens: int,
    input_krw_per_mtok: float,
    output_krw_per_mtok: float,
) -> float:
    """Return the KRW cost for one call given token counts + unit prices.

    Pricing convention is **per million tokens** (matches Anthropic's
    published unit). We divide by 1_000_000 so callers can pass the same
    numbers they read from Anthropic's pricing page.

    Raises:
        ValueError: if either token count is negative. Negative tokens
            indicate a bug in the SDK adapter and would silently produce
            a credit to the cost meter, which is worse than a hard fail.
    """
    if input_tokens < 0 or output_tokens < 0:
        raise ValueError(
            f"Token counts must be non-negative; got input={input_tokens}, "
            f"output={output_tokens}"
        )

    input_cost = (input_tokens / 1_000_000.0) * input_krw_per_mtok
    output_cost = (output_tokens / 1_000_000.0) * output_krw_per_mtok
    return input_cost + output_cost


@dataclass(frozen=True, slots=True)
class CostRecord:
    """One LLM call's contribution to a reading's cost.

    Frozen so the audit list cannot be mutated after the fact — the
    cost-model dashboard needs immutable history.
    """

    model: str
    input_tokens: int
    output_tokens: int
    unit_price_in: float  # KRW per million input tokens
    unit_price_out: float  # KRW per million output tokens
    total_krw: float


@dataclass
class CostTracker:
    """In-memory accumulator for `CostRecord` entries.

    One instance per logical "session" (reading, follow-up turn, tarot,
    etc.). The pipeline orchestrator constructs it, passes it to every
    LLM call, then reads ``total_krw()`` to write to
    ``Reading.cost_krw``.
    """

    records: list[CostRecord] = field(default_factory=list)

    def record(
        self,
        *,
        model: str,
        input_tokens: int,
        output_tokens: int,
        input_krw_per_mtok: float,
        output_krw_per_mtok: float,
    ) -> CostRecord:
        """Compute KRW and append a `CostRecord`.

        Returns the inserted record so callers can log it directly.
        """
        total = compute_call_krw(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            input_krw_per_mtok=input_krw_per_mtok,
            output_krw_per_mtok=output_krw_per_mtok,
        )
        rec = CostRecord(
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            unit_price_in=input_krw_per_mtok,
            unit_price_out=output_krw_per_mtok,
            total_krw=total,
        )
        self.records.append(rec)
        return rec

    def total_krw(self) -> float:
        """Sum of per-call KRW (the value persisted to ``Reading.cost_krw``)."""
        return sum(r.total_krw for r in self.records)

    def total_input_tokens(self) -> int:
        return sum(r.input_tokens for r in self.records)

    def total_output_tokens(self) -> int:
        return sum(r.output_tokens for r in self.records)


__all__ = [
    "CostRecord",
    "CostTracker",
    "compute_call_krw",
]
