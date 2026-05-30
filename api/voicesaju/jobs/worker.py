"""Worker entry point (ISSUE-038, Phase-1).

Two execution modes:

1. **Production (Phase-2)** — ``WorkerSettings`` is the contract arq
   expects to discover a worker module via ``arq voicesaju.jobs.worker``.
   The ``functions`` list registers the callable that arq's Redis-backed
   poll loop invokes. We do NOT pin ``arq>=…`` as a hard dependency in
   Phase-1 — the package ships the structure, ISSUE-074/075 lands the
   Redis wiring.

2. **Phase-1 tests / local dev** — ``InMemoryQueue`` is a tiny in-process
   queue that round-trips jobs without a Redis. ``enqueue()`` accepts
   ``(function_name, *args, **kwargs)`` and runs the matching registered
   function in the same event loop. Tests use this to exercise the
   worker → job dispatch path hermetically.

The architecture §8.4 keeps the worker → finalize boundary thin so
swapping the queue implementation is a 5-line diff.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

# Public registry of job names → coroutines. The real arq worker
# expects ``WorkerSettings.functions`` to be a list of callables; the
# in-memory stub uses the name (callable.__name__) as the dispatch key.
# We expose the same registry to both so callers don't have to maintain
# two copies of the function list.
_JOB_REGISTRY: dict[str, Callable[..., Awaitable[Any]]] = {}


def register(func: Callable[..., Awaitable[Any]]) -> Callable[..., Awaitable[Any]]:
    """Decorator: register *func* under its ``__name__`` for dispatch."""
    _JOB_REGISTRY[func.__name__] = func
    return func


# Populate the registry at import time. The import side-effect is
# intentional — this is how arq discovers callables, and the in-memory
# stub piggybacks on the same module-level state.
from voicesaju.jobs.audio_finalize import finalize_audio  # noqa: E402

register(finalize_audio)


class WorkerSettings:
    """arq-compatible settings object.

    arq's CLI does ``import voicesaju.jobs.worker:WorkerSettings`` and
    inspects ``functions`` to learn what to dispatch. We list every
    registered job so the production worker mirrors the in-memory
    queue's coverage.

    Redis URL is read from env at the time arq boots — we don't pin
    it here so tests that import this module don't touch the env.
    """

    functions: list[Callable[..., Awaitable[Any]]] = list(_JOB_REGISTRY.values())

    # Tunable knobs. Defaults are conservative — concrete values land
    # alongside the Redis deploy (ISSUE-074).
    max_jobs: int = 4
    job_timeout: int = 30  # seconds; audio finalize is CPU-light + fast.


# ---------------------------------------------------------------------------
# In-memory queue (Phase-1 tests / local dev)
# ---------------------------------------------------------------------------


class InMemoryQueue:
    """Round-trips jobs through an in-process queue, no Redis required.

    Usage::

        queue = InMemoryQueue()
        await queue.enqueue("finalize_audio", reading_id="abc", ...)
        results = await queue.drain()  # runs every queued job

    Tests use ``drain()`` so the assertion can sit at the same await
    point as the worker's poll loop would in production.
    """

    def __init__(self) -> None:
        self._pending: list[tuple[str, tuple[Any, ...], dict[str, Any]]] = []

    async def enqueue(self, name: str, *args: Any, **kwargs: Any) -> None:
        """Append a job onto the queue. Does NOT execute it yet."""
        if name not in _JOB_REGISTRY:
            raise KeyError(
                f"no registered job named {name!r}; registered: {sorted(_JOB_REGISTRY)}"
            )
        self._pending.append((name, args, kwargs))

    async def drain(self) -> list[Any]:
        """Execute every queued job in FIFO order; return the results."""
        results: list[Any] = []
        while self._pending:
            name, args, kwargs = self._pending.pop(0)
            func = _JOB_REGISTRY[name]
            results.append(await func(*args, **kwargs))
        return results

    def __len__(self) -> int:
        return len(self._pending)


async def enqueue(
    queue: InMemoryQueue,
    name: str,
    *args: Any,
    **kwargs: Any,
) -> None:
    """Convenience wrapper so callers can stay in `from voicesaju.jobs`.

    Mirrors arq's enqueue signature — the real Redis-backed enqueue
    will share the same name once ISSUE-074 lands.
    """
    await queue.enqueue(name, *args, **kwargs)


def _ensure_event_loop() -> asyncio.AbstractEventLoop:
    """Belt-and-suspenders helper used by the real arq main loop.

    Re-exposed only so importing ``voicesaju.jobs.worker`` from a sync
    script (e.g. a deploy preflight) works without a running event loop.
    """
    try:
        return asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        return loop


__all__ = [
    "InMemoryQueue",
    "WorkerSettings",
    "enqueue",
    "register",
]
