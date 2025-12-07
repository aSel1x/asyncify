from collections.abc import AsyncIterator, Callable, Coroutine, Iterable
from typing import TypedDict, TypeVar

T = TypeVar('T')
R = TypeVar('R')


# Function types
SyncFunc = Callable[..., R]  # Sync function returning R
AsyncFunc = Callable[..., Coroutine[None, None, R]]  # Async function returning R
SyncOrAsyncFunc = (
    Callable[..., object] | Callable[..., Coroutine[None, None, object]]
)  # Either sync or async

# Callback type
Callback = Callable[[R], None]

# Generator types
SyncGenerator = Callable[..., Iterable[T]]  # Function returning sync generator/iterator
AsyncGenerator = AsyncIterator[T]  # Async generator
ChunkedAsyncGenerator = AsyncIterator[list[T]]  # Async generator yielding chunks

# Executor types
ExecutorFunc = Callable[..., R]  # Function type for executor.submit()
Initializer = Callable[..., object]  # Pool worker initialization function
InitializerArgs = tuple[object, ...]  # Arguments for initializer function


# Internal task result
class TaskResult(TypedDict, total=False):
    """Task execution result with either success or error."""

    ok: bool  # True if successful, False if error
    result: object  # Result value if ok=True
    exc: BaseException  # Exception if ok=False
