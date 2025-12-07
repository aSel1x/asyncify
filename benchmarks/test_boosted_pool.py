"""Demo/example usage of BoostedProcessPool features."""

import time

from asyncify.core.executors import BOOSTED_POOL


def cpu_task(n: int) -> int:
    """Example CPU task."""
    return sum(i * i for i in range(n))


def demo_basic_usage():
    """Demonstrate basic pool usage."""
    print("\n=== Demo: Basic Usage ===")

    future = BOOSTED_POOL.submit(cpu_task, 1000)
    result = future.result(timeout=5.0)
    print(f"Result: {result}")
    print("✓ Basic submit and result retrieval")


def demo_callbacks():
    """Demonstrate callback usage."""
    print("\n=== Demo: Callbacks ===")

    results: list[object] = []
    errors: list[str] = []

    def on_success(result: object) -> None:
        results.append(result)
        print(f"✓ Success callback received: {result}")

    def on_error(error: BaseException) -> None:
        errors.append(str(error))
        print(f"✗ Error callback received: {error}")

    future = BOOSTED_POOL.submit(
        cpu_task, 500, on_success=on_success, on_error=on_error
    )

    _ = future.result(timeout=5.0)
    time.sleep(0.1)
    print(f"Total successful: {len(results)}")


def demo_priority_and_channels():
    """Demonstrate priority levels and channels."""
    print("\n=== Demo: Priority & Channels ===")

    BOOSTED_POOL.create_channel("high_priority")

    futures = [
        BOOSTED_POOL.submit(cpu_task, 500, priority=0, channel="default"),
        BOOSTED_POOL.submit(cpu_task, 500, priority=2, channel="high_priority"),
        BOOSTED_POOL.submit(cpu_task, 500, priority=1, channel="default"),
    ]

    results = [f.result(timeout=5.0) for f in futures]
    print(f"✓ Completed {len(results)} tasks across channels")


def demo_sticky_workers():
    """Demonstrate sticky worker assignment."""
    print("\n=== Demo: Sticky Workers ===")

    futures = [
        BOOSTED_POOL.submit(cpu_task, 500, sticky_id=0),
        BOOSTED_POOL.submit(cpu_task, 500, sticky_id=1),
        BOOSTED_POOL.submit(cpu_task, 500, sticky_id=0),
        BOOSTED_POOL.submit(cpu_task, 500, sticky_id=1),
    ]

    results = [f.result(timeout=5.0) for f in futures]
    print(f"✓ Completed {len(results)} tasks with sticky assignment")


def demo_stats():
    """Demonstrate pool statistics."""
    print("\n=== Demo: Pool Statistics ===")

    stats = BOOSTED_POOL.stats()
    print(f"Max workers: {stats.max_workers}")
    print(f"Queue lengths: {stats.queue_lengths}")
    print(f"Worker loads: {stats.worker_loads}")
    print(f"CPU utilization: {stats.cpu_util}")
    print("✓ Statistics retrieved")


def main():
    """Run all demos."""
    print("=" * 60)
    print("  BOOSTED POOL FEATURE DEMOS")
    print("=" * 60)

    demo_basic_usage()
    demo_callbacks()
    demo_priority_and_channels()
    demo_sticky_workers()
    demo_stats()

    print("\n" + "=" * 60)
    print("  ALL DEMOS COMPLETED")
    print("=" * 60)


if __name__ == "__main__":
    main()
