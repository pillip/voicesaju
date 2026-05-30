"""Tests for the storage adapter Protocol + MockStorageAdapter (ISSUE-038)."""

from __future__ import annotations

import pytest

from voicesaju.adapters.storage import (
    MockStorageAdapter,
    R2StorageAdapter,
    content_sha256,
)


@pytest.mark.asyncio
async def test_mock_put_get_roundtrip(tmp_path):
    adapter = MockStorageAdapter(root=tmp_path)
    url = await adapter.put_object(
        "audio/readings/r1/main.mp3", b"\xff\xfb\x90\x00data"
    )
    assert (
        url.startswith("file://") or url.startswith("/") or "audio/readings/r1" in url
    )

    got = await adapter.get_object("audio/readings/r1/main.mp3")
    assert got == b"\xff\xfb\x90\x00data"


@pytest.mark.asyncio
async def test_mock_list_objects_returns_sorted_keys(tmp_path):
    adapter = MockStorageAdapter(root=tmp_path)
    await adapter.put_object("audio/readings/r1/chunks/0002.mp3", b"\xff\xfbB")
    await adapter.put_object("audio/readings/r1/chunks/0000.mp3", b"\xff\xfb0")
    await adapter.put_object("audio/readings/r1/chunks/0001.mp3", b"\xff\xfbA")

    keys = await adapter.list_objects("audio/readings/r1/chunks")
    assert keys == [
        "audio/readings/r1/chunks/0000.mp3",
        "audio/readings/r1/chunks/0001.mp3",
        "audio/readings/r1/chunks/0002.mp3",
    ]


@pytest.mark.asyncio
async def test_mock_delete_object_removes(tmp_path):
    adapter = MockStorageAdapter(root=tmp_path)
    await adapter.put_object("k", b"x")
    await adapter.delete_object("k")
    with pytest.raises((FileNotFoundError, KeyError)):
        await adapter.get_object("k")


@pytest.mark.asyncio
async def test_r2_adapter_raises_until_phase2():
    adapter = R2StorageAdapter()
    with pytest.raises(NotImplementedError):
        await adapter.put_object("k", b"x")


def test_content_sha256_is_deterministic():
    assert content_sha256(b"hello") == content_sha256(b"hello")
    assert content_sha256(b"hello") != content_sha256(b"world")
    # 64-char hex digest
    assert len(content_sha256(b"x")) == 64
