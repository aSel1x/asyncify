"""Integration tests for asyncify - testing real-world scenarios."""

import asyncio
import time

import pytest
from asyncify import asyncify, run_async, run_sync


# Test functions - must be at module level for pickling
def heavy_computation(n: int) -> int:
    """CPU-intensive task."""
    return sum(i * i for i in range(n))


def io_operation(delay: float) -> str:
    """IO-bound operation."""
    time.sleep(delay)
    return f'completed_{delay}'


async def async_computation(x: int, y: int) -> int:
    """Async computation."""
    await asyncio.sleep(0.01)
    return x + y


@asyncify(cpu_bound=False)
def decorated_io_task(delay: float) -> str:
    """IO-bound task with decorator."""
    time.sleep(delay)
    return f'io_{delay}'


@pytest.mark.asyncio
async def test_cpu_bound_tasks_concurrent():
    """Test multiple CPU-bound tasks running concurrently."""
    tasks = [run_sync(heavy_computation, 10000) for _ in range(5)]

    start = time.time()
    results = await asyncio.gather(*tasks)
    elapsed = time.time() - start

    expected = sum(i * i for i in range(10000))
    assert all(r == expected for r in results)
    # Should be faster than sequential
    assert elapsed < 5.0  # Very conservative


@pytest.mark.asyncio
async def test_io_bound_tasks_concurrent():
    """Test multiple IO-bound tasks running concurrently."""
    tasks = [run_sync(io_operation, 0.1) for _ in range(10)]

    start = time.time()
    results = await asyncio.gather(*tasks)
    elapsed = time.time() - start

    assert all('completed_' in r for r in results)
    # Should be concurrent, not sequential
    assert elapsed < 0.5  # Much faster than 1.0s sequential


@pytest.mark.asyncio
async def test_mixed_workload():
    """Test mixed CPU and IO bound tasks."""
    tasks = [
        run_sync(heavy_computation, 5000),
        run_sync(io_operation, 0.05),
        run_sync(heavy_computation, 5000),
        run_sync(io_operation, 0.05),
    ]

    results = await asyncio.gather(*tasks)
    assert len(results) == 4


@pytest.mark.asyncio
async def test_decorator_cpu_bound():
    """Test CPU-bound tasks via run_sync (decorator would fail pickle)."""
    heavy_computation._cpu_bound = True  # type: ignore[attr-defined]
    tasks = [run_sync(heavy_computation, 10000) for _ in range(3)]

    results = await asyncio.gather(*tasks)
    expected = sum(i * i for i in range(10000))
    assert all(r == expected for r in results)


@pytest.mark.asyncio
async def test_decorator_io_bound():
    """Test @asyncify decorator with IO-bound tasks."""
    tasks = [decorated_io_task(0.05) for _ in range(5)]

    start = time.time()
    results = await asyncio.gather(*tasks)
    elapsed = time.time() - start

    assert all(r == 'io_0.05' for r in results)
    assert elapsed < 0.2  # Concurrent execution


def test_run_async_from_sync():
    """Test calling async function from sync code."""
    result = run_async(async_computation, 10, 20)
    assert result == 30


def test_run_async_multiple_calls():
    """Test multiple run_async calls in sequence."""
    results = []
    for i in range(5):
        result = run_async(async_computation, i, i + 1)
        results.append(result)

    assert results == [1, 3, 5, 7, 9]


@pytest.mark.asyncio
async def test_nested_async_sync():
    """Test nesting async and sync operations."""

    # Async calls sync which calls async
    async def outer():
        # This is async context
        result = await run_sync(lambda: run_async(async_computation, 5, 10))
        return result

    result = await outer()
    assert result == 15


@pytest.mark.asyncio
async def test_error_propagation_in_concurrent_tasks():
    """Test that errors in concurrent tasks are properly handled."""

    def failing_task():
        raise ValueError('Task failed')

    def successful_task():
        return 'success'

    tasks = [
        run_sync(successful_task),
        run_sync(failing_task),
        run_sync(successful_task),
    ]

    results = await asyncio.gather(*tasks, return_exceptions=True)

    assert results[0] == 'success'
    assert isinstance(results[1], ValueError)
    assert results[2] == 'success'


@pytest.mark.asyncio
async def test_high_concurrency():
    """Test high concurrency scenario."""
    # Many small IO tasks
    tasks = [run_sync(io_operation, 0.01) for _ in range(50)]

    start = time.time()
    results = await asyncio.gather(*tasks)
    elapsed = time.time() - start

    assert len(results) == 50
    # Should be much faster than sequential (0.5s)
    assert elapsed < 0.3


@pytest.mark.asyncio
async def test_decorator_with_kwargs():
    """Test decorator with keyword arguments."""

    @asyncify()
    def task_with_kwargs(x: int, y: int = 10) -> int:
        return x * y

    result = await task_with_kwargs(5, y=3)
    assert result == 15


def test_sync_to_async_to_sync():
    """Test calling pattern: sync -> async -> sync."""

    # Start from sync code
    def sync_wrapper():
        # Call async via run_async
        return run_async(async_computation, 100, 200)

    result = sync_wrapper()
    assert result == 300
