"""Performance benchmarks for asyncify library."""

import asyncio
import time

from asyncify import asyncify, run_sync


def cpu_task(n: int) -> int:
    """Simulate CPU-intensive work."""
    return sum(i * i for i in range(n))


def io_task(delay: float = 0.1) -> str:
    """Simulate IO-bound work."""
    time.sleep(delay)
    return f'Completed after {delay}s'


@asyncify(cpu_bound=True)
def decorated_cpu_task(n: int) -> int:
    """CPU task decorated with @asyncify."""
    return sum(i * i for i in range(n))


@asyncify(cpu_bound=False)
def decorated_io_task(delay: float = 0.1) -> str:
    """IO task decorated with @asyncify."""
    time.sleep(delay)
    return f'Completed after {delay}s'


async def benchmark_cpu_async():
    """Benchmark CPU tasks via run_sync."""
    print('\n=== CPU-bound Benchmark (via run_sync) ===')
    num_tasks = 10
    n = 100_000

    # Mark as CPU-bound
    cpu_task._cpu_bound = True

    start = time.time()
    tasks = [run_sync(cpu_task, n) for _ in range(num_tasks)]
    results = await asyncio.gather(*tasks)
    elapsed = time.time() - start

    print(f'Tasks: {num_tasks} x sum(i²) for i in range({n:,})')
    print(f'Elapsed: {elapsed:.3f}s')
    print(f'Avg per task: {elapsed / num_tasks:.3f}s')
    print(f'All completed: {len(results) == num_tasks}')


async def benchmark_io_async():
    """Benchmark IO tasks via run_sync."""
    print('\n=== IO-bound Benchmark (via run_sync) ===')
    num_tasks = 20
    delay = 0.1

    start = time.time()
    tasks = [run_sync(io_task, delay) for _ in range(num_tasks)]
    results = await asyncio.gather(*tasks)
    elapsed = time.time() - start

    print(f'Tasks: {num_tasks} x {delay}s delay')
    print(f'Elapsed: {elapsed:.3f}s')
    print(f'Expected: ~{delay:.3f}s (concurrent)')
    print(f'All completed: {len(results) == num_tasks}')


async def benchmark_async_mixed():
    """Benchmark mixed CPU + IO tasks in async context."""
    print('\n=== Mixed Async Benchmark ===')

    # Mix of CPU and IO tasks
    tasks = [
        decorated_cpu_task(50_000),
        decorated_io_task(0.1),
        decorated_cpu_task(50_000),
        decorated_io_task(0.1),
        run_sync(cpu_task, 50_000),
        run_sync(io_task, 0.1),
    ]

    start = time.time()
    results = await asyncio.gather(*tasks)
    elapsed = time.time() - start

    print('Tasks: 3x CPU + 3x IO')
    print(f'Elapsed: {elapsed:.3f}s')
    print(f'All completed: {len(results) == len(tasks)}')


async def benchmark_concurrent_decorator():
    """Benchmark concurrent execution with @asyncify decorator."""
    print('\n=== Concurrent @asyncify Benchmark ===')
    num_tasks = 10

    tasks = [decorated_io_task(0.05) for _ in range(num_tasks)]

    start = time.time()
    results = await asyncio.gather(*tasks)
    elapsed = time.time() - start

    print(f'Tasks: {num_tasks} x 0.05s delay')
    print(f'Elapsed: {elapsed:.3f}s')
    print('Expected: ~0.05s (concurrent)')
    print(f'Speedup: {(0.05 * num_tasks) / elapsed:.1f}x')


async def main():
    """Run all benchmarks."""
    print('=' * 60)
    print('  ASYNCIFY PERFORMANCE BENCHMARKS')
    print('=' * 60)

    await benchmark_cpu_async()
    await benchmark_io_async()
    await benchmark_async_mixed()
    await benchmark_concurrent_decorator()

    print('\n' + '=' * 60)
    print('  BENCHMARKS COMPLETED')
    print('=' * 60)


if __name__ == '__main__':
    asyncio.run(main())
