from collections.abc import Awaitable, Callable
from functools import wraps
from typing import ParamSpec, TypeVar

from asyncify.core.runners import run_sync
from asyncify.types import R

P = ParamSpec('P')
T = TypeVar('T')


def asyncify(
    cpu_bound: bool = False,
) -> Callable[[Callable[P, R]], Callable[P, Awaitable[R]]]:
    """
    Декоратор для превращения sync функции в async.
    
    Использует run_sync для выполнения в thread/process pool.
    
    Args:
        cpu_bound: Если True, использует ProcessPoolExecutor для CPU-bound задач.
                   Если False, использует ThreadPoolExecutor для IO-bound задач.
    
    Returns:
        Async версия функции
    
    Example:
        ```python
        @asyncify()
        def read_file(path: str) -> str:
            with open(path) as f:
                return f.read()
        
        # Теперь можно вызывать async
        content = await read_file('data.txt')
        
        # Для CPU-bound задач
        @asyncify(cpu_bound=True)
        def heavy_compute(n: int) -> int:
            return sum(i * i for i in range(n))
        
        result = await heavy_compute(10_000_000)
        ```
    """

    def decorator(func: Callable[P, R]) -> Callable[P, Awaitable[R]]:
        if cpu_bound:
            setattr(func, '_cpu_bound', True)

        @wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            return await run_sync(func, *args, **kwargs)

        return wrapper

    return decorator
