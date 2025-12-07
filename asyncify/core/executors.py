import atexit
import concurrent.futures
import multiprocessing

from .boosted_pool import BoostedProcessPool

CPU_COUNT = multiprocessing.cpu_count()

THREAD_POOL = concurrent.futures.ThreadPoolExecutor(
    max_workers=max(32, CPU_COUNT * 4), thread_name_prefix="asyncify-thread"
)

BOOSTED_POOL = BoostedProcessPool(
    max_workers=max(1, CPU_COUNT),
    warmup=True,
    sticky=True,
    priority_levels=3,
    preload_initializer=None,
    adaptive=True,
)


def _cleanup_pools() -> None:
    """Cleanup pools on exit."""
    try:
        _ = BOOSTED_POOL.shutdown(wait=False, cancel_pending=True)
        THREAD_POOL.shutdown(wait=False, cancel_futures=True)
    except Exception:
        pass


_ = atexit.register(_cleanup_pools)
