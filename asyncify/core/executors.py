# asyncify/executors.py
import atexit
import concurrent.futures
import multiprocessing

from .boosted_pool import BoostedProcessPool

CPU_COUNT = multiprocessing.cpu_count()

# Thread pool for IO-bound tasks
# Adaptive size: min 32, max 4 * CPU_COUNT for high I/O concurrency
THREAD_POOL = concurrent.futures.ThreadPoolExecutor(
    max_workers=max(32, CPU_COUNT * 4), thread_name_prefix='asyncify-thread'
)

# Use boosted deluxe pool for CPU-bound tasks
# create as module-level singleton so run_sync can use it
BOOSTED_POOL = BoostedProcessPool(
    max_workers=max(1, CPU_COUNT),
    warmup=True,
    sticky=True,
    priority_levels=3,
    preload_initializer=None,  # set to function if you want per-worker preload
    adaptive=True,
)


def _cleanup_pools() -> None:
    """Clean up executor pools on program exit."""
    # Note: ProcessPoolExecutor's atexit может зависать
    # В тестах используем os._exit(0) для обхода этой проблемы
    try:
        _ = BOOSTED_POOL.shutdown(wait=False, cancel_pending=True)
        THREAD_POOL.shutdown(wait=False, cancel_futures=True)
    except Exception:
        pass


_ = atexit.register(_cleanup_pools)
