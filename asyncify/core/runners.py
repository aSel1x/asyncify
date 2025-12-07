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
    """Сentinel объект для обозначения конца генератора."""

    __slots__ = ()


_STOP: Final = _StopSentinel()


async def run_sync_iter(
    sync_gen_func: SyncGenerator[T],
    *args: object,
    chunk_size: int = 1,
    max_queue_size: int | None = None,
    **kwargs: object,
) -> AsyncGenerator[list[T]]:
    """
    Превращает sync generator -> async generator.

    Поддержка:
      - Потоковая передача элементов без полной буферизации
      - Backpressure через asyncio.Queue(maxsize)
      - Chunked processing через chunk_size
      - Неблокирующая передача данных через run_coroutine_threadsafe

    Args:
        sync_gen_func: Функция, возвращающая sync генератор
        chunk_size: Размер chunk'а для батчинга элементов
        max_queue_size: Максимальный размер очереди (по умолчанию chunk_size * 4)

    Yields:
        Списки элементов размером до chunk_size
    """
    loop = asyncio.get_running_loop()
    max_queue_size = max_queue_size or chunk_size * 4
    queue: Queue[T | _StopSentinel | BaseException] = asyncio.Queue(maxsize=max_queue_size)

    def producer() -> None:
        """
        Producer запускается в ThreadPool, добавляет элементы в очередь.
        Использует run_coroutine_threadsafe для неблокирующей передачи.
        """
        try:
            for item in sync_gen_func(*args, **kwargs):
                # Используем run_coroutine_threadsafe вместо blocking sleep
                future = asyncio.run_coroutine_threadsafe(queue.put(item), loop)
                future.result()  # Ждём пока элемент добавится (backpressure)
        except BaseException as e:
            # Передаём исключение в consumer
            future = asyncio.run_coroutine_threadsafe(queue.put(e), loop)
            future.result()
        finally:
            # Обозначаем конец генератора
            future = asyncio.run_coroutine_threadsafe(queue.put(_STOP), loop)
            future.result()

    # Запуск sync генератора в ThreadPool
    _ = loop.run_in_executor(THREAD_POOL, producer)

    buffer: list[T] = []
    while True:
        item = await queue.get()
        if isinstance(item, _StopSentinel):
            if buffer:
                yield buffer
            break
        if isinstance(item, BaseException):
            # Пробрасываем исключение из producer
            raise item
        # Теперь TypeChecker понимает что item: T
        buffer.append(item)
        if len(buffer) >= chunk_size:
            yield buffer
            buffer = []


async def run_sync(
    func: SyncFunc[R],
    *args: object,
    executor: Executor | None = None,
    **kwargs: object,
) -> R:
    """
    Execute sync function in a thread or process pool without blocking event loop.
    Supports:
      - THREAD_POOL for IO-bound
      - BOOSTED_POOL for CPU-bound
    """
    loop = asyncio.get_running_loop()

    # explicit executor
    if executor is not None:
        return await loop.run_in_executor(executor, partial(func, *args, **kwargs))

    # auto choose
    if getattr(func, '_cpu_bound', False):
        # Напрямую через ProcessPool для CPU-bound - избегаем лишнего ThreadPool
        fut = BOOSTED_POOL.submit_direct(func, *args, **kwargs)
        # Ждём результат в executor чтобы не блокировать event loop
        return await asyncio.wrap_future(fut)
    else:
        return await loop.run_in_executor(THREAD_POOL, partial(func, *args, **kwargs))


def run_async(
    awaitable: Callable[..., Awaitable[R]],
    *args: object,
    **kwargs: object,
) -> R:
    """
    Запускает async-функцию внутри sync-кода.

    Создаёт новый event loop в отдельном потоке, чтобы избежать конфликтов
    с существующими event loops.

    Args:
        awaitable: Async функция для выполнения
        *args: Позиционные аргументы
        **kwargs: Именованные аргументы

    Returns:
        Результат выполнения async функции

    Example:
        ```python
        async def fetch_data(url: str) -> dict:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as resp:
                    return await resp.json()

        # Вызов из sync кода
        data = run_async(fetch_data, 'https://api.example.com/data')
        ```

    Warning:
        Функция блокирует текущий поток до завершения async функции.
    """

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
    t.join(timeout=300)  # 5 минут timeout по умолчанию

    if t.is_alive():
        raise TimeoutError('Async function execution timeout (300s)')
    
    if not result:
        raise RuntimeError('No result from async function')
    
    value = result[0]
    if isinstance(value, BaseException):
        raise value
    return value
