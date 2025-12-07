"""Tests for run_sync function."""

import asyncio
import time

import pytest

from asyncify import run_sync


def sync_add(x: int, y: int) -> int:
    """Simple sync addition."""
    return x + y


def sync_io_task(delay: float = 0.05) -> str:
    """IO-bound sync task."""
    time.sleep(delay)
    return "done"


def sync_cpu_task(n: int) -> int:
    """CPU-bound sync task."""
    return sum(i * i for i in range(n))


def failing_task() -> None:
    """Task that always fails."""
    raise RuntimeError("Task failed")


@pytest.mark.asyncio
async def test_run_sync_basic():
    """Test basic run_sync call."""
    result = await run_sync(sync_add, 2, 3)
    assert result == 5


@pytest.mark.asyncio
async def test_run_sync_kwargs():
    """Test run_sync with keyword arguments."""
    result = await run_sync(sync_add, x=10, y=20)
    assert result == 30


@pytest.mark.asyncio
async def test_run_sync_io_bound():
    """Test run_sync with IO-bound task."""
    result = await run_sync(sync_io_task, delay=0.02)
    assert result == "done"


@pytest.mark.asyncio
async def test_run_sync_cpu_bound():
    """Test run_sync with CPU-bound task (marked with _cpu_bound)."""
    # Mark function as CPU-bound
    sync_cpu_task._cpu_bound = True  # type: ignore[attr-defined]

    result = await run_sync(sync_cpu_task, 100)
    expected = sum(i * i for i in range(100))
    assert result == expected


@pytest.mark.asyncio
async def test_run_sync_concurrent():
    """Test concurrent execution with run_sync."""
    tasks = [run_sync(sync_io_task, delay=0.05) for _ in range(5)]
    start = time.time()
    results = await asyncio.gather(*tasks)
    elapsed = time.time() - start

    assert all(r == "done" for r in results)
    # Should take ~0.05s with concurrency, not 0.25s
    assert elapsed < 0.15


@pytest.mark.asyncio
async def test_run_sync_exception():
    """Test that exceptions are properly propagated."""
    with pytest.raises(RuntimeError, match="Task failed"):
        await run_sync(failing_task)
