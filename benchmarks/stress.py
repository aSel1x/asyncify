"""Stress tests for asyncify library - high load scenarios."""

import asyncio
import time
from collections.abc import Awaitable

from asyncify import asyncify, run_sync


def cpu_task(n: int) -> int:
    """CPU-intensive calculation."""
    return sum(i * i for i in range(n))


def io_task(delay: float = 0.05) -> float:
    """IO-bound task with delay."""
    time.sleep(delay)
    return delay


@asyncify(cpu_bound=True)
def decorated_cpu_task(n: int) -> int:
    """Decorated CPU task."""
    return sum(i * i for i in range(n))


async def stress_cpu_async():
    """Stress test with many CPU tasks."""
    print("\n=== CPU Stress Test ===")
    num_tasks = 100
    n = 10_000

    tasks = [run_sync(cpu_task, n, cpu_bound=True) for _ in range(num_tasks)]

    start = time.time()
    results = await asyncio.gather(*tasks, return_exceptions=True)
    elapsed = time.time() - start

    completed = sum(1 for r in results if not isinstance(r, Exception))
    failed = sum(1 for r in results if isinstance(r, Exception))

    print(f"Tasks submitted: {num_tasks}")
    print(f"Completed: {completed}")
    print(f"Failed: {failed}")
    print(f"Elapsed: {elapsed:.2f}s")
    print(f"Throughput: {num_tasks / elapsed:.1f} tasks/sec")


async def stress_io_async():
    """Stress test with many IO tasks."""
    print("\n=== IO Stress Test ===")
    num_tasks = 200
    delay = 0.05

    tasks = [run_sync(io_task, delay) for _ in range(num_tasks)]

    start = time.time()
    results = await asyncio.gather(*tasks)
    elapsed = time.time() - start

    print(f"Tasks: {num_tasks} x {delay}s delay")
    print(f"Completed: {len(results)}")
    print(f"Elapsed: {elapsed:.2f}s")
    print(f"Throughput: {num_tasks / elapsed:.1f} tasks/sec")
    print(f"Expected ~{delay}s with high concurrency")


async def stress_async_mixed():
    """Stress test with mixed CPU and IO async tasks."""
    print("\n=== Mixed Async Stress Test ===")

    tasks: list[Awaitable[int | float]] = []
    for _ in range(50):
        tasks.append(decorated_cpu_task(5_000))
    for _ in range(50):
        tasks.append(run_sync(io_task, 0.03))

    start = time.time()
    results: list[object] = await asyncio.gather(*tasks, return_exceptions=True)
    elapsed = time.time() - start

    successful = sum(1 for r in results if not isinstance(r, Exception))
    failed = sum(1 for r in results if isinstance(r, Exception))

    print(f"Total tasks: {len(tasks)}")
    print(f"Successful: {successful}")
    print(f"Failed: {failed}")
    print(f"Elapsed: {elapsed:.2f}s")
    print(f"Throughput: {len(tasks) / elapsed:.1f} tasks/sec")


async def stress_concurrent_decorator():
    """Stress test for @asyncify decorator with high concurrency."""
    print("\n=== Decorator Concurrency Stress Test ===")
    num_tasks = 100

    tasks = [decorated_cpu_task(10_000) for _ in range(num_tasks)]

    start = time.time()
    results = await asyncio.gather(*tasks, return_exceptions=True)
    elapsed = time.time() - start

    successful = sum(1 for r in results if not isinstance(r, Exception))

    print(f"Tasks: {num_tasks}")
    print(f"Successful: {successful}")
    print(f"Elapsed: {elapsed:.2f}s")
    print(f"Throughput: {num_tasks / elapsed:.1f} tasks/sec")


async def main():
    """Run all stress tests."""
    print("=" * 60)
    print("  ASYNCIFY STRESS TESTS")
    print("=" * 60)

    await stress_cpu_async()
    await stress_io_async()
    await stress_async_mixed()
    await stress_concurrent_decorator()

    print("\n" + "=" * 60)
    print("  STRESS TESTS COMPLETED")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
