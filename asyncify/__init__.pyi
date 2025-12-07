"""Type stubs for asyncify."""

from collections.abc import Awaitable, Callable
from concurrent.futures import Executor
from typing import TypeVar

from asyncify.types import AsyncGenerator, SyncFunc, SyncGenerator

R = TypeVar("R")
T = TypeVar("T")

def run_sync(
    func: SyncFunc[R],
    *args: object,
    executor: Executor | None = None,
    cpu_bound: bool | None = None,
    **kwargs: object,
) -> Awaitable[R]:
    """
    Execute sync function in thread/process pool without blocking event loop.

    Args:
        func: Sync function to execute
        *args: Positional arguments for func
        executor: Explicit executor (overrides cpu_bound)
        cpu_bound: True=ProcessPool, False=ThreadPool, None=auto-detect via _cpu_bound
        **kwargs: Keyword arguments for func

    Returns:
        Awaitable that resolves to func's return value

    Example:
        ```python
        # Auto-detect via _cpu_bound attribute
        result = await run_sync(func)

        # Explicit CPU-bound (ProcessPool)
        result = await run_sync(bcrypt.hashpw, password, salt, cpu_bound=True)

        # Explicit IO-bound (ThreadPool)
        result = await run_sync(requests.get, url, cpu_bound=False)
        ```
    """
def run_async(
    awaitable: Callable[..., Awaitable[R]],
    *args: object,
    **kwargs: object,
) -> R:
    """
    Run async function from sync code (blocks current thread).

    Args:
        awaitable: Async function to execute
        *args: Positional arguments for awaitable
        **kwargs: Keyword arguments for awaitable

    Returns:
        Result from async function

    Raises:
        TimeoutError: If execution exceeds 300s
        RuntimeError: If no result returned

    Example:
        ```python
        # Run async function from sync context
        result = run_async(fetch_data, url="https://example.com")
        ```
    """

def run_sync_iter(
    sync_gen_func: SyncGenerator[T],
    *args: object,
    chunk_size: int = 1,
    max_queue_size: int | None = None,
    **kwargs: object,
) -> AsyncGenerator[list[T]]:
    """
    Convert sync generator to async with chunking and backpressure.

    Args:
        sync_gen_func: Sync generator function
        *args: Positional arguments for sync_gen_func
        chunk_size: Items per yielded chunk (default: 1)
        max_queue_size: Max queue size for backpressure (default: chunk_size * 4)
        **kwargs: Keyword arguments for sync_gen_func

    Yields:
        Lists of items with size up to chunk_size

    Example:
        ```python
        async for batch in run_sync_iter(read_large_file, chunk_size=100):
            await process_batch(batch)
        ```
    """

def asyncify(
    cpu_bound: bool = False,
) -> Callable[[Callable[..., R]], Callable[..., Awaitable[R]]]:
    """
    Decorator to convert sync function to async using run_sync.

    Args:
        cpu_bound: If True, uses ProcessPool; if False, uses ThreadPool

    Returns:
        Decorator that wraps sync function as async

    Example:
        ```python
        @asyncify(cpu_bound=True)
        def heavy_computation(n: int) -> int:
            return sum(i**2 for i in range(n))

        result = await heavy_computation(1000000)
        ```
    """

__all__ = [
    "run_sync",
    "run_async",
    "run_sync_iter",
    "asyncify",
]
