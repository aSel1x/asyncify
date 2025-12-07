"""Tests for run_sync_iter function."""

from collections.abc import Generator

import pytest

from asyncify import run_sync_iter


def number_generator(n: int) -> Generator[int, None, None]:
    """Generate numbers from 0 to n-1."""
    for i in range(n):
        yield i


def string_generator() -> Generator[str, None, None]:
    """Generate some strings."""
    for word in ["hello", "world", "test"]:
        yield word


@pytest.mark.asyncio
async def test_run_sync_iter_basic():
    """Test basic sync generator to async generator conversion."""
    items: list[int] = []
    async for chunk in run_sync_iter(number_generator, 5):
        items.extend(chunk)
    assert items == [0, 1, 2, 3, 4]


@pytest.mark.asyncio
async def test_run_sync_iter_with_chunks():
    """Test chunked iteration."""
    chunks: list[list[int]] = []
    async for chunk in run_sync_iter(number_generator, 10, chunk_size=3):
        chunks.append(chunk)

    # Should have chunks of size 3, 3, 3, 1
    assert len(chunks) == 4
    assert chunks[0] == [0, 1, 2]
    assert chunks[1] == [3, 4, 5]
    assert chunks[2] == [6, 7, 8]
    assert chunks[3] == [9]


@pytest.mark.asyncio
async def test_run_sync_iter_strings():
    """Test with non-numeric types."""
    items: list[str] = []
    async for chunk in run_sync_iter(string_generator):
        items.extend(chunk)
    assert items == ["hello", "world", "test"]


@pytest.mark.asyncio
async def test_run_sync_iter_empty():
    """Test with empty generator."""

    def empty_gen() -> Generator[int, None, None]:
        return
        yield  # Make it a generator

    items: list[int] = []
    async for chunk in run_sync_iter(empty_gen):
        items.extend(chunk)
    assert items == []
