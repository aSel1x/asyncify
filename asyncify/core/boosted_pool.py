import atexit
import concurrent.futures
import multiprocessing
import os
import queue
import random
import threading
import time
from _thread import LockType
from concurrent.futures.process import ProcessPoolExecutor
from dataclasses import dataclass
from threading import Event, Thread
from typing import Callable, TypeVar, final

try:
    import psutil
except ImportError:
    psutil = None

from asyncify.types import Initializer, InitializerArgs, SyncOrAsyncFunc, TaskResult

SubmitResult = TypeVar("SubmitResult")


@dataclass
class PoolStats:
    max_workers: int
    queue_lengths: dict[str, list[int]]
    worker_loads: list[int]
    cpu_util: float | None = None
    throttle_delay: float = 0.0  # Текущая задержка для throttling


@final
class _TaskItem:
    """Internal task item for BoostedProcessPool."""

    __slots__ = (
        "fn",
        "args",
        "kwargs",
        "priority",
        "sticky_id",
        "channel",
        "retries_left",
        "backoff",
        "attempt",
        "on_success",
        "on_error",
        "user_future",
    )

    def __init__(
        self,
        fn: SyncOrAsyncFunc,
        args: tuple[object, ...] = (),
        kwargs: dict[str, object] | None = None,
        priority: int = 1,
        sticky_id: int | None = None,
        channel: str = "default",
        retries: int = 0,
        backoff: float = 0.5,
        on_success: Callable[[object], None] | None = None,
        on_error: Callable[[BaseException], None] | None = None,
    ) -> None:
        self.fn: SyncOrAsyncFunc = fn
        self.args: tuple[object, ...] = args or ()
        self.kwargs: dict[str, object] = kwargs or {}
        self.priority: int = max(0, priority)
        self.sticky_id: int | None = sticky_id
        self.channel: str = channel or "default"
        self.retries_left: int = retries
        self.backoff: float = backoff
        self.attempt: int = 0
        self.on_success: Callable[[object], None] | None = on_success
        self.on_error: Callable[[BaseException], None] | None = on_error
        self.user_future: FutureLike | None = None


@final
class _VirtualWorker:
    """Virtual worker для отслеживания нагрузки на воркеры пула."""

    __slots__ = ("idx", "load", "_lock")

    def __init__(self, idx: int) -> None:
        self.idx: int = idx
        self.load: int = 0
        self._lock: LockType = threading.Lock()

    def reserve(self) -> None:
        with self._lock:
            self.load += 1

    def release(self) -> None:
        with self._lock:
            self.load = max(0, self.load - 1)


@final
class FutureLike:
    """
    Обёртка для user-facing future-like объекта.

    Warning:
        Не вызывайте result() из того же потока, что и executor!
        Это может привести к deadlock. Используйте callbacks вместо этого.
    """

    __slots__ = ("_done_event", "_result", "_exception")

    def __init__(self) -> None:
        self._done_event: Event = threading.Event()
        self._result: object | None = None
        self._exception: BaseException | None = None

    def set_result(self, result: object) -> None:
        self._result = result
        self._done_event.set()

    def set_exception(self, exc: BaseException) -> None:
        self._exception = exc
        self._done_event.set()

    def result(self, timeout: float | None = None) -> object:
        """
        Ждёт завершения задачи и возвращает результат.

        Args:
            timeout: Максимальное время ожидания в секундах

        Returns:
            Результат выполнения задачи

        Raises:
            TimeoutError: Если задача не завершилась за timeout
            BaseException: Исключение из задачи, если она упала
        """
        if not self._done_event.wait(timeout):
            raise TimeoutError()
        if self._exception:
            raise self._exception
        return self._result

    def done(self) -> bool:
        return self._done_event.is_set()


class BoostedProcessPool:
    """
    Продвинутый process pool с поддержкой:
    - Priority queues (приоритизация задач)
    - Sticky workers (привязка задач к конкретным workers)
    - Channels (группировка задач по каналам)
    - Retry механизм с exponential backoff
    - CPU monitoring и адаптивная загрузка
    - Callbacks для обработки результатов/ошибок

    Example:
        ```python
        pool = BoostedProcessPool(
            max_workers=4,
            warmup=True,
            sticky=True,
            priority_levels=3
        )

        # Submit с приоритетом и callbacks
        future = pool.submit(
            heavy_task,
            data,
            priority=2,
            on_success=lambda r: print(f"Done: {r}"),
            on_error=lambda e: print(f"Error: {e}")
        )

        result = future.result(timeout=10.0)
        pool.shutdown(wait=True)
        ```
    """

    def __init__(
        self,
        max_workers: int | None = None,
        warmup: bool = True,
        sticky: bool = True,
        priority_levels: int = 3,
        preload_initializer: Initializer | None = None,
        preload_args: InitializerArgs | None = None,
        adaptive: bool = True,
    ) -> None:
        self.max_workers: int = max_workers or max(1, multiprocessing.cpu_count())
        self.priority_levels: int = max(1, priority_levels)
        self.sticky: bool = sticky
        self.adaptive: bool = adaptive

        self._pool: ProcessPoolExecutor
        if preload_initializer is not None:
            initargs: InitializerArgs = preload_args or ()
            self._pool = concurrent.futures.ProcessPoolExecutor(
                max_workers=self.max_workers,
                initializer=preload_initializer,
                initargs=initargs,
            )
        else:
            self._pool = concurrent.futures.ProcessPoolExecutor(
                max_workers=self.max_workers
            )

        self.virtual_workers: list[_VirtualWorker] = [
            _VirtualWorker(i) for i in range(self.max_workers)
        ]
        self._channels: dict[str, tuple[queue.Queue[_TaskItem], ...]] = {}
        self._channels_lock: LockType = threading.Lock()
        self._ensure_channel("default")
        self._task_available: Event = threading.Event()

        self._throttle_delay: float = 0.0
        self._throttle_lock: LockType = threading.Lock()

        self._running: bool = True
        self._dispatcher: Thread = threading.Thread(
            target=self._dispatcher_loop, daemon=True
        )
        self._dispatcher.start()

        self._future_to_info: dict[
            concurrent.futures.Future[TaskResult],
            tuple[_TaskItem, _VirtualWorker],
        ] = {}
        self._future_lock: LockType = threading.Lock()

        self._monitor: Thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._monitor.start()

        if warmup:
            self._warmup()

        _ = atexit.register(self.shutdown)

    def _ensure_channel(self, name: str) -> None:
        with self._channels_lock:
            if name not in self._channels:
                self._channels[name] = tuple(
                    queue.Queue[_TaskItem]() for _ in range(self.priority_levels)
                )

    def create_channel(self, name: str) -> None:
        self._ensure_channel(name)

    def submit_direct(
        self, func: Callable[..., SubmitResult], *args: object, **kwargs: object
    ) -> concurrent.futures.Future[SubmitResult]:
        """
        Прямой доступ к underlying ProcessPoolExecutor для low-level операций.
        Используется в run_sync для CPU-bound задач.
        """
        fut: concurrent.futures.Future[SubmitResult] = self._pool.submit(
            func, *args, **kwargs
        )
        return fut

    def _warmup(self) -> None:
        """Warmup: запускаем простые задачи чтобы поднять все процессы."""
        futures = [self._pool.submit(lambda: 1) for _ in range(self.max_workers)]
        for f in futures:
            try:
                _ = f.result(timeout=1)
            except Exception:
                pass  # Игнорируем ошибки warmup
        time.sleep(0.03)  # Небольшая задержка для стабилизации

    # Submit with callback & future
    def submit(
        self,
        fn: SyncOrAsyncFunc,
        *args: object,
        priority: int = 1,
        sticky_id: int | None = None,
        channel: str = "default",
        retries: int = 0,
        backoff: float = 0.5,
        on_success: Callable[[object], None] | None = None,
        on_error: Callable[[BaseException], None] | None = None,
    ) -> FutureLike:
        """
        Enqueue task, optionally attach callbacks for success/error.

        Args:
            fn: Функция для выполнения
            priority: Приоритет задачи (0 = lowest)
            sticky_id: ID для привязки к конкретному worker
            channel: Канал для группировки задач
            retries: Количество повторов при ошибке
            backoff: Базовая задержка для exponential backoff
            on_success: Callback для успешного выполнения
            on_error: Callback для обработки ошибок

        Returns:
            FutureLike объект для ожидания результата
        """
        self._ensure_channel(channel)
        task = _TaskItem(
            fn,
            args,
            priority=priority,
            sticky_id=sticky_id,
            channel=channel,
            retries=retries,
            backoff=backoff,
            on_success=on_success,
            on_error=on_error,
        )
        future_like = FutureLike()
        task.user_future = future_like
        q = self._channels[channel][min(priority, self.priority_levels - 1)]
        q.put(task)
        _ = self._task_available.set()  # Сигнализируем dispatcher
        return future_like

    # Dispatcher loop
    def _dispatcher_loop(self) -> None:
        while self._running:
            _ = self._task_available.wait(timeout=0.1)
            self._task_available.clear()

            while self._running:
                task = self._pop_task()
                if task is None:
                    break

                with self._throttle_lock:
                    delay = self._throttle_delay
                if delay > 0:
                    time.sleep(delay)

                worker: _VirtualWorker = (
                    self.virtual_workers[task.sticky_id % self.max_workers]
                    if (self.sticky and task.sticky_id is not None)
                    else min(self.virtual_workers, key=lambda w: w.load)
                )
                worker.reserve()
                fut = self._pool.submit(self._execute_task_wrapper, task)
                with self._future_lock:
                    self._future_to_info[fut] = (task, worker)
                fut.add_done_callback(self._on_task_done)

    def _pop_task(self) -> _TaskItem | None:
        with self._channels_lock:
            for _ch, queues in self._channels.items():
                for q in queues:
                    try:
                        return q.get_nowait()
                    except queue.Empty:
                        continue
        return None

    @staticmethod
    def _execute_task_wrapper(task: _TaskItem) -> TaskResult:
        try:
            return {"ok": True, "result": task.fn(*task.args, **task.kwargs)}
        except Exception as e:
            return {"ok": False, "exc": e}

    def _on_task_done(self, fut: concurrent.futures.Future[TaskResult]) -> None:
        with self._future_lock:
            mapping = self._future_to_info.pop(fut, None)
        if mapping is None:
            return
        task, worker = mapping
        worker.release()
        try:
            res = fut.result()
        except Exception as e:
            failed = True
            exc: BaseException | None = e
            result_val: object | None = None
        else:
            failed = not res.get("ok", False)
            exc_val = res.get("exc", None)
            exc = exc_val if isinstance(exc_val, BaseException) else None
            result_val = res.get("result", None)

        if failed and task.retries_left > 0:
            task.retries_left -= 1
            task.attempt += 1
            backoff_factor: float = task.backoff
            attempt_count: int = task.attempt - 1
            exponential_factor: float = pow(2.0, attempt_count)
            delay_time: float = (
                backoff_factor * exponential_factor + random.random() * 0.05
            )
            threading.Timer(delay_time, lambda: self._requeue(task)).start()
            return
        # set future
        if task.user_future is not None:
            if failed and exc is not None:
                task.user_future.set_exception(exc)
            elif failed:
                task.user_future.set_exception(
                    RuntimeError("Task failed without exception")
                )
            else:
                task.user_future.set_result(
                    result_val if result_val is not None else None
                )

        # call appropriate callback
        if not failed and task.on_success is not None:
            try:
                task.on_success(result_val)
            except Exception:
                pass  # Игнорируем ошибки в callback
        elif failed and exc is not None and task.on_error is not None:
            try:
                task.on_error(exc)
            except Exception:
                pass  # Игнорируем ошибки в callback

    def _requeue(self, task: _TaskItem) -> None:
        q = self._channels[task.channel][min(task.priority, self.priority_levels - 1)]
        q.put(task)
        _ = self._task_available.set()  # Сигнализируем dispatcher

    # ----------------------
    # Monitoring & stats
    # ----------------------
    def _measure_cpu_util(self) -> float | None:
        """
        Измеряет использование CPU.

        Использует:
        1. psutil.cpu_percent() если доступен (pip install asyncify[monitoring])
        2. os.getloadavg() на Unix-системах как fallback
        3. None если ни один метод не доступен
        """
        try:
            if psutil is not None:
                u = psutil.cpu_percent(interval=None) / 100.0
                if u == 0.0:
                    u = psutil.cpu_percent(interval=0.1) / 100.0
                return max(0.0, min(1.0, u))
            elif hasattr(os, "getloadavg"):
                load1 = os.getloadavg()[0]
                cpu = os.cpu_count() or 1
                return max(0.0, min(1.0, load1 / cpu))
            return None
        except Exception:
            return None

    def _monitor_loop(self) -> None:
        """Мониторинг CPU и adaptive scaling."""
        cpu_history: list[float] = []
        max_history = 10  # Последние 10 измерений для сглаживания

        while self._running and self.adaptive:
            time.sleep(1.0)
            cpu_util = self._measure_cpu_util()

            if cpu_util is None:
                continue

            # Собираем историю для сглаживания скачков
            cpu_history.append(cpu_util)
            if len(cpu_history) > max_history:
                _ = cpu_history.pop(0)

            # Средняя загрузка за последние измерения
            avg_cpu = sum(cpu_history) / len(cpu_history)

            # Adaptive throttling на основе средней загрузки
            if len(cpu_history) >= 5:
                with self._throttle_lock:
                    if avg_cpu > 0.9:
                        # CPU перегружен - увеличиваем задержку между задачами
                        self._throttle_delay = min(0.1, self._throttle_delay + 0.01)
                    elif avg_cpu > 0.75:
                        # CPU загружен умеренно - небольшая задержка
                        self._throttle_delay = min(0.05, self._throttle_delay + 0.005)
                    elif avg_cpu < 0.5:
                        # CPU недогружен - убираем задержку
                        self._throttle_delay = max(0.0, self._throttle_delay - 0.01)
                    elif avg_cpu < 0.7:
                        # CPU нормально - плавно снижаем задержку
                        self._throttle_delay = max(0.0, self._throttle_delay - 0.005)

    def stats(self) -> PoolStats:
        with self._channels_lock:
            qlens = {
                ch: [q.qsize() for q in queues] for ch, queues in self._channels.items()
            }
        loads = [w.load for w in self.virtual_workers]
        cpu: float | None = self._measure_cpu_util()
        with self._throttle_lock:
            throttle = self._throttle_delay
        return PoolStats(
            max_workers=self.max_workers,
            queue_lengths=qlens,
            worker_loads=loads,
            cpu_util=cpu,
            throttle_delay=throttle,
        )

    def _all_queues_empty(self) -> bool:
        """Проверяет, что все очереди пусты."""
        with self._channels_lock:
            return all(q.empty() for queues in self._channels.values() for q in queues)

    def _all_workers_idle(self) -> bool:
        """Проверяет, что все workers idle (нет активных задач)."""
        return all(w.load == 0 for w in self.virtual_workers)

    def shutdown(
        self,
        wait: bool = True,
        timeout: float | None = None,
        cancel_pending: bool = False,
    ) -> bool:
        """
        Останавливает pool и освобождает ресурсы.

        Args:
            wait: Если True, ждёт завершения всех задач в очереди
            timeout: Максимальное время ожидания в секундах (только если wait=True)
            cancel_pending: Если True,
            отменяет задачи в очереди (игнорируется если wait=True)

        Returns:
            True если все задачи завершились, False если timeout

        Example:
            # Graceful shutdown - ждёт все задачи
            pool.shutdown(wait=True, timeout=10.0)

            # Fast shutdown - отменяет pending задачи
            pool.shutdown(wait=False, cancel_pending=True)
        """
        if wait:
            # Graceful shutdown: ждём пока очереди опустеют и workers станут idle
            start_time = time.time()
            while not (self._all_queues_empty() and self._all_workers_idle()):
                if timeout is not None and (time.time() - start_time) >= timeout:
                    break  # Timeout - переходим к forced shutdown
                time.sleep(0.05)

        # Останавливаем dispatcher и monitor
        self._running = False
        try:
            self._dispatcher.join(timeout=0.5)
            self._monitor.join(timeout=0.5)
        except Exception:
            pass

        # Закрываем underlying pool
        try:
            self._pool.shutdown(cancel_futures=cancel_pending, wait=wait)
        except Exception:
            pass  # Игнорируем ошибки shutdown - pool может быть уже закрыт

        # Проверяем успешность завершения
        return self._all_queues_empty() and self._all_workers_idle()
