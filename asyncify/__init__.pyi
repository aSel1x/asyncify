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
) -> Awaitable[R]: ...
def run_async(
    awaitable: Callable[..., Awaitable[R]],
    *args: object,
    **kwargs: object,
) -> R: ...
def run_sync_iter(
    sync_gen_func: SyncGenerator[T],
    *args: object,
    chunk_size: int = 1,
    max_queue_size: int | None = None,
    **kwargs: object,
) -> AsyncGenerator[list[T]]: ...
def asyncify(
    cpu_bound: bool = False,
) -> Callable[[Callable[..., R]], Callable[..., Awaitable[R]]]: ...

__all__ = [
    "run_sync",
    "run_async",
    "run_sync_iter",
    "asyncify",
]
