"""arq worker smoke (ISSUE-038 AC3): importable + InMemoryQueue round-trips."""

from __future__ import annotations

import pytest

from voicesaju.jobs.worker import _JOB_REGISTRY, InMemoryQueue, WorkerSettings

pytestmark = pytest.mark.integration


def test_worker_settings_lists_finalize_audio():
    """arq imports ``WorkerSettings.functions`` to learn registered jobs."""
    names = {f.__name__ for f in WorkerSettings.functions}
    assert "finalize_audio" in names


def test_registry_has_finalize_audio():
    assert "finalize_audio" in _JOB_REGISTRY


@pytest.mark.asyncio
async def test_in_memory_queue_round_trips():
    """Enqueue → drain runs the job in FIFO order."""

    async def _job(x: int) -> int:
        return x * 2

    # Hot-patch a job that doesn't need a DB session.
    _JOB_REGISTRY["double"] = _job
    try:
        q = InMemoryQueue()
        await q.enqueue("double", 7)
        await q.enqueue("double", 21)
        results = await q.drain()
        assert results == [14, 42]
        assert len(q) == 0
    finally:
        _JOB_REGISTRY.pop("double", None)


@pytest.mark.asyncio
async def test_in_memory_queue_rejects_unknown_job():
    q = InMemoryQueue()
    with pytest.raises(KeyError, match="no registered job"):
        await q.enqueue("does_not_exist", 1)
