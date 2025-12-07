import asyncio
import threading
from asyncio.queues import Queue
from collections.abc import Awaitable, Callable
from concurrent.futures import Executor
from functools import partial
from typing import Final, final

from asyncify.core.executors import BOOSTED_POOL, THREAD_POOL
from asyncify.types import AsyncGenerator, R, SyncFunc, SyncGenerator, T


@final
class _StopSentinel:
    """Sentinel for generator end."""

    __slots__ = ()


_STOP: Final = _StopSentinel()


async def run_sync_iter(
    sync_gen_func: SyncGenerator[T],
    *args: object,
    chunk_size: int = 1,
    max_queue_size: int | None = None,
    **kwargs: object,
) -> AsyncGenerator[list[T]]:
    """Convert sync generator to async with chunking and backpressure."""
    loop = asyncio.get_running_loop()
    max_queue_size = max_queue_size or chunk_size * 4
    queue: Queue[T | _StopSentinel | BaseException] = asyncio.Queue(
        maxsize=max_queue_size
    )

    def producer() -> None:
        """Producer runs in ThreadPool, adds items to queue."""
        try:
            for item in sync_gen_func(*args, **kwargs):
                future = asyncio.run_coroutine_threadsafe(queue.put(item), loop)
                future.result()
        except BaseException as e:
            future = asyncio.run_coroutine_threadsafe(queue.put(e), loop)
            future.result()
        finally:
            future = asyncio.run_coroutine_threadsafe(queue.put(_STOP), loop)
            future.result()

    _ = loop.run_in_executor(THREAD_POOL, producer)

    buffer: list[T] = []
    while True:
        item = await queue.get()
        if isinstance(item, _StopSentinel):
            if buffer:
                yield buffer
            break
        if isinstance(item, BaseException):
            raise item

        buffer.append(item)
        if len(buffer) >= chunk_size:
            yield buffer
            buffer = []


async def run_sync(
    func: SyncFunc[R],
    *args: object,
    executor: Executor | None = None,
    cpu_bound: bool | None = None,
    **kwargs: object,
) -> R:
    """Execute sync function in thread/process pool without blocking event loop."""
    loop = asyncio.get_running_loop()

    if executor is not None:
        return await loop.run_in_executor(executor, partial(func, *args, **kwargs))

    is_cpu_bound = (
        cpu_bound if cpu_bound is not None else getattr(func, "_cpu_bound", False)
    )

    if is_cpu_bound:
        fut = BOOSTED_POOL.submit_direct(func, *args, **kwargs)
        return await asyncio.wrap_future(fut)
    else:
        return await loop.run_in_executor(THREAD_POOL, partial(func, *args, **kwargs))


def run_async(
    awaitable: Callable[..., Awaitable[R]],
    *args: object,
    **kwargs: object,
) -> R:
    """Run async function from sync code (blocks current thread)."""

    result: list[R | BaseException] = []

    def runner() -> None:
        loop: asyncio.AbstractEventLoop | None = None
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            res = loop.run_until_complete(awaitable(*args, **kwargs))
            result.append(res)
        except BaseException as e:
            result.append(e)
        finally:
            if loop is not None:
                loop.close()

    t = threading.Thread(target=runner, daemon=True)
    t.start()
    t.join(timeout=300)

    if t.is_alive():
        raise TimeoutError("Async function execution timeout (300s)")

    if not result:
        raise RuntimeError("No result from async function")

    value = result[0]
    if isinstance(value, BaseException):
        raise value
    return value
