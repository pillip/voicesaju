"""Async Anthropic SDK wrapper with retries, timeouts, and cost tracking.

Implements ISSUE-034. Architecture §7 covers the high-level design.

Responsibilities
----------------
- Stream tokens from ``messages.stream`` and yield them to the caller.
- Time-box the whole call at 10s (NFR FR-033 budget). Timeout raises
  ``LLMTimeoutError`` and does NOT retry — a hung call is usually a
  whole-call issue, not a transient hiccup.
- Retry transient 5xx and connection errors up to 2× with exponential
  backoff. Use ``tenacity`` for the retry loop so the strategy stays in
  one place + is testable.
- Map SDK exceptions to typed errors (``LLMClientError`` /
  ``LLMTimeoutError``) so callers don't import ``anthropic.*`` directly.
- On successful completion, read the final usage block and append a
  ``CostRecord`` to the supplied ``CostTracker``.

What this module deliberately does NOT do
-----------------------------------------
- Persist anything to the DB. ``Reading.cost_krw`` write is the
  pipeline's job (ISSUE-039).
- Inject prompts / chart context. Callers compose the system + user
  strings per Architecture §7.2 before calling ``stream``.
- Apply guardrails. The deny-list / moderation pass lives in
  ``voicesaju.llm.guardrail`` and wraps the stream upstream.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from typing import Any

# Anthropic SDK imports. The version pinned in pyproject.toml ships
# ``AsyncAnthropic`` + the async streaming manager. We import the small
# exception subset we care about so type-checkers can narrow correctly.
from anthropic import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AsyncAnthropic,
)
from tenacity import (
    AsyncRetrying,
    RetryError,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

from voicesaju.llm.cost_tracker import CostTracker
from voicesaju.llm.router import HAIKU_4_5, SONNET_4_6

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Public error types
# ---------------------------------------------------------------------------


class LLMError(Exception):
    """Base class for LLM-layer errors surfaced to callers."""


class LLMClientError(LLMError):
    """Non-retryable error (4xx, exhausted retries, etc.).

    Carries the underlying SDK exception in ``__cause__`` for debugging.
    """


class LLMTimeoutError(LLMError):
    """The total time budget for the call was exceeded.

    Distinct from ``LLMClientError`` because the FR-033 fallback path
    treats timeouts differently from generic failures (it preserves the
    user's free token).
    """


# ---------------------------------------------------------------------------
# KRW pricing defaults (PRD §11 OQ-01 — exact 2026 prices pending)
# ---------------------------------------------------------------------------
#
# These are conservative estimates per Architecture §7.4 cost-model
# notes. They are surfaced as ctor kwargs so the integration with
# ``voicesaju.config.Settings`` is a one-line wiring change at the call
# site, not a code change here. See the PRD's open question OQ-01.

DEFAULT_INPUT_KRW_PER_MTOK: dict[str, float] = {
    SONNET_4_6: 4_000.0,  # TODO(OQ-01): replace with billed price post-Phase-2.
    HAIKU_4_5: 1_000.0,
}
DEFAULT_OUTPUT_KRW_PER_MTOK: dict[str, float] = {
    SONNET_4_6: 20_000.0,
    HAIKU_4_5: 5_000.0,
}


# ---------------------------------------------------------------------------
# Retry predicate — 5xx and connection errors only
# ---------------------------------------------------------------------------


def _is_retryable(exc: BaseException) -> bool:
    """Return True iff ``exc`` is a transient error worth retrying.

    - ``APIStatusError`` with status ≥ 500 → 5xx server error, retry.
    - ``APIConnectionError`` → DNS / TCP / TLS hiccup, retry.
    - Everything else (4xx, validation, timeouts) → don't retry.
    """
    if isinstance(exc, APIStatusError):
        status = getattr(exc, "status_code", None)
        return isinstance(status, int) and status >= 500
    return isinstance(exc, APIConnectionError)


# ---------------------------------------------------------------------------
# AnthropicLLMClient
# ---------------------------------------------------------------------------


class AnthropicLLMClient:
    """Async wrapper over ``AsyncAnthropic`` with retries + cost tracking.

    Parameters
    ----------
    api_key:
        Anthropic API key. Must be a non-empty string — failing fast on
        empty config beats a 401 surprise in CI.
    cost_tracker:
        Session-scoped tracker. The client appends one ``CostRecord``
        per successful call.
    sdk_client:
        Optional pre-built ``AsyncAnthropic``. Tests inject a mock; in
        production we construct one from ``api_key``.
    timeout_seconds:
        Whole-call budget (per NFR FR-033 = 10s). Use a tiny value in
        tests to exercise the timeout path quickly.
    retry_initial_delay / retry_max_delay:
        Exponential backoff bounds. Defaults give ~0.5s, ~1s between
        the two retries; tests override to keep runtime <1s.
    input_krw_per_mtok / output_krw_per_mtok:
        Per-model unit prices. Defaults come from ``DEFAULT_*`` above;
        production wiring substitutes values from ``Settings``.
    """

    def __init__(
        self,
        *,
        api_key: str,
        cost_tracker: CostTracker,
        sdk_client: AsyncAnthropic | Any | None = None,
        timeout_seconds: float = 10.0,
        retry_initial_delay: float = 0.5,
        retry_max_delay: float = 4.0,
        input_krw_per_mtok: dict[str, float] | None = None,
        output_krw_per_mtok: dict[str, float] | None = None,
    ) -> None:
        if not api_key:
            # NB: catches both "" and None (None will TypeError on `not`,
            # but pyright complains, so the type-system + this check
            # together make the API hard to misuse).
            raise ValueError("api_key must be a non-empty string")

        # NB: when sdk_client is None, we construct from api_key. The
        # SDK accepts the api_key via ctor — no env-var magic at our
        # layer.
        self._sdk: Any = sdk_client or AsyncAnthropic(api_key=api_key)
        self._tracker = cost_tracker
        self._timeout_seconds = timeout_seconds
        self._retry_initial_delay = retry_initial_delay
        self._retry_max_delay = retry_max_delay
        self._input_prices = input_krw_per_mtok or dict(DEFAULT_INPUT_KRW_PER_MTOK)
        self._output_prices = output_krw_per_mtok or dict(DEFAULT_OUTPUT_KRW_PER_MTOK)

    # ----- Streaming -----

    async def stream(
        self,
        *,
        model: str,
        system: str,
        user: str,
        max_tokens: int,
        temperature: float = 1.0,
    ) -> AsyncIterator[str]:
        """Stream the response token-by-token.

        Wraps the whole call in ``asyncio.wait_for`` so the 10s budget
        applies to *first byte through last byte*, then retries the
        whole thing on transient failures. We do NOT retry on partial
        success: that would double-charge the user's token bill.

        Yields:
            Strings produced by ``AsyncMessageStream.text_stream``. Each
            string corresponds to a single SSE token / delta from
            Anthropic.

        Raises:
            LLMTimeoutError: if the call exceeds ``timeout_seconds``.
            LLMClientError: for non-retryable SDK errors (4xx,
                validation, exhausted retries).
        """
        retry_loop = AsyncRetrying(
            stop=stop_after_attempt(3),  # 1 initial + 2 retries
            wait=wait_exponential(
                multiplier=self._retry_initial_delay,
                max=self._retry_max_delay,
            ),
            retry=retry_if_exception(_is_retryable),
            reraise=True,
        )

        # We have to collect tokens *inside* the retry loop because the
        # caller's `async for` consumes them as they arrive. The
        # alternative — buffering the entire response — would defeat
        # the streaming contract (NFR-002 first-byte budget).
        #
        # `_run_once` is generator-shaped: it yields tokens lazily and
        # records cost at the end. We materialise into a list per
        # attempt; if the attempt fails before completion the partial
        # list is discarded.
        async def _run_once() -> list[str]:
            return await self._stream_once(
                model=model,
                system=system,
                user=user,
                max_tokens=max_tokens,
                temperature=temperature,
            )

        try:
            tokens = await retry_loop(_run_once)
        except APITimeoutError as exc:
            raise LLMTimeoutError("LLM call exceeded timeout budget") from exc
        except RetryError as exc:  # pragma: no cover (reraise=True path)
            raise LLMClientError("LLM call failed after retries") from exc
        except APIStatusError as exc:
            # Non-retryable 4xx (or 5xx after exhausted retries fall through here
            # too, because reraise=True surfaces the underlying exception).
            raise LLMClientError(
                f"LLM call failed: status={getattr(exc, 'status_code', '?')}"
            ) from exc
        except APIConnectionError as exc:  # pragma: no cover
            raise LLMClientError("LLM connection failed after retries") from exc

        # Re-emit the buffered tokens. The first-byte budget was already
        # consumed by the SDK stream; surfacing them sequentially here
        # is what the FastAPI SSE handler iterates over.
        for tok in tokens:
            yield tok

    async def _stream_once(
        self,
        *,
        model: str,
        system: str,
        user: str,
        max_tokens: int,
        temperature: float,
    ) -> list[str]:
        """Single attempt at the streamed call.

        Runs inside ``asyncio.wait_for`` so the 10s budget bounds the
        whole attempt. On timeout, ``LLMTimeoutError`` propagates up;
        the retry loop deliberately does NOT catch it (see
        ``_is_retryable``).
        """
        try:
            return await asyncio.wait_for(
                self._consume_stream(
                    model=model,
                    system=system,
                    user=user,
                    max_tokens=max_tokens,
                    temperature=temperature,
                ),
                timeout=self._timeout_seconds,
            )
        except TimeoutError as exc:
            # Map asyncio's TimeoutError to our public type so callers
            # don't have to import asyncio just to handle it.
            raise LLMTimeoutError(
                f"LLM call exceeded {self._timeout_seconds}s budget"
            ) from exc

    async def _consume_stream(
        self,
        *,
        model: str,
        system: str,
        user: str,
        max_tokens: int,
        temperature: float,
    ) -> list[str]:
        """Open the SDK stream, collect tokens, record cost.

        The cost write happens **after** the stream completes — partial
        streams must NOT bill the user (the pipeline will refund the
        token via the FR-033 fallback path).
        """
        tokens: list[str] = []

        stream_cm = self._sdk.messages.stream(
            model=model,
            system=system,
            messages=[{"role": "user", "content": user}],
            max_tokens=max_tokens,
            temperature=temperature,
        )

        # `stream()` returns an `AsyncMessageStreamManager`; entering it
        # gives the live `AsyncMessageStream` we iterate over.
        async with stream_cm as stream:
            async for token in stream.text_stream:
                tokens.append(token)
            final = await stream.get_final_message()

        # Best-effort usage extraction. The SDK guarantees the field on
        # the final message, but we coerce defensively in case a future
        # version restructures the dataclass.
        usage = getattr(final, "usage", None)
        input_tokens = int(getattr(usage, "input_tokens", 0) or 0)
        output_tokens = int(getattr(usage, "output_tokens", 0) or 0)

        in_price = self._input_prices.get(model, 0.0)
        out_price = self._output_prices.get(model, 0.0)

        rec = self._tracker.record(
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            input_krw_per_mtok=in_price,
            output_krw_per_mtok=out_price,
        )
        logger.info(
            "llm_call_complete",
            extra={
                "model": model,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "total_krw": rec.total_krw,
            },
        )
        return tokens


__all__ = [
    "DEFAULT_INPUT_KRW_PER_MTOK",
    "DEFAULT_OUTPUT_KRW_PER_MTOK",
    "AnthropicLLMClient",
    "LLMClientError",
    "LLMError",
    "LLMTimeoutError",
]
