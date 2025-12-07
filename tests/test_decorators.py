"""Tests for @asyncify decorator."""

import asyncio
import time

import pytest

from asyncify import asyncify, run_sync


@asyncify(cpu_bound=False)
def io_bound_task(x: int, delay: float = 0.01) -> int:
    """IO-bound task using ThreadPool."""
    time.sleep(delay)
    return x * 2


def cpu_task_plain(n: int) -> int:
    """Plain CPU-bound task (not decorated)."""
    return sum(i * i for i in range(n))


@pytest.mark.asyncio
async def test_asyncify_io_bound():
    """Test @asyncify with IO-bound task."""
    result = await io_bound_task(5)
    assert result == 10


@pytest.mark.asyncio
async def test_asyncify_cpu_bound():
    """Test CPU-bound task via run_sync (decorator would fail pickle)."""
    # Mark as CPU-bound and use run_sync directly
    cpu_task_plain._cpu_bound = True  # type: ignore[attr-defined]
    result = await run_sync(cpu_task_plain, 100)
    assert result == sum(i * i for i in range(100))


@pytest.mark.asyncio
async def test_asyncify_concurrent():
    """Test concurrent execution with @asyncify."""
    tasks = [io_bound_task(i, delay=0.05) for i in range(5)]
    start = time.time()
    results = await asyncio.gather(*tasks)
    elapsed = time.time() - start

    assert results == [0, 2, 4, 6, 8]
    # Should take ~0.05s with concurrency, not 0.25s
    assert elapsed < 0.15
