from collections.abc import Awaitable, Callable
from functools import wraps
from typing import ParamSpec, TypeVar

from asyncify.core.runners import run_sync
from asyncify.types import R

P = ParamSpec("P")
T = TypeVar("T")


def asyncify(
    cpu_bound: bool = False,
) -> Callable[[Callable[P, R]], Callable[P, Awaitable[R]]]:
    """Decorator to convert sync function to async using run_sync."""

    def decorator(func: Callable[P, R]) -> Callable[P, Awaitable[R]]:
        @wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            return await run_sync(func, *args, **kwargs, cpu_bound=cpu_bound)

        return wrapper

    return decorator
