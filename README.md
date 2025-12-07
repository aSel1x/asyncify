# asyncify

**Bridge between sync and async Python code**

Simple, type-safe library for seamless async/sync interoperability with automatic thread/process pool management.

## Features

- 🔄 **`run_sync`** - Execute sync functions in async context (auto thread/process pool)
- ⚡ **`run_async`** - Execute async functions in sync context
- 🔁 **`run_sync_iter`** - Convert sync generators to async generators
- 🎨 **`@asyncify`** - Decorator for sync → async conversion
- 🚀 **Auto-detection** - Automatic CPU/IO-bound task detection via `_cpu_bound` attribute
- 📊 **Adaptive throttling** - CPU monitoring and dynamic workload management
- ✅ **Type-safe** - Full type hints, 0 basedpyright errors

## Installation

```bash
# Basic installation
uv add asyncify

# With CPU monitoring support (optional)
uv add 'asyncify[monitoring]'
```

## Quick Start

### 1. Sync → Async (run_sync)

```python
import asyncio
import time
from asyncify import run_sync

# IO-bound task (uses ThreadPoolExecutor)
def fetch_data(url: str) -> str:
    time.sleep(0.1)  # Simulate network I/O
    return f"Data from {url}"

# CPU-bound task (uses ProcessPoolExecutor)
def heavy_compute(n: int) -> int:
    return sum(i * i for i in range(n))


async def main():
    # IO-bound - automatic ThreadPool
    result = await run_sync(fetch_data, "https://example.com")
    print(result)
    
    # CPU-bound - mark with _cpu_bound for ProcessPool
    heavy_compute._cpu_bound = True
    result = await run_sync(heavy_compute, 1_000_000)
    print(result)

asyncio.run(main())
```

### 2. Async → Sync (run_async)

```python
from asyncify import run_async

async def async_operation(x: int, y: int) -> int:
    await asyncio.sleep(0.1)
    return x + y

# Call async from sync code
result = run_async(async_operation, 10, 20)
print(result)  # 30
```

### 3. Sync Generator → Async Generator (run_sync_iter)

```python
from asyncify import run_sync_iter

def number_generator(n: int):
    for i in range(n):
        time.sleep(0.01)  # Simulate work
        yield i

async def main():
    async for chunk in run_sync_iter(number_generator, 100, chunk_size=10):
        print(f"Received chunk: {chunk}")

asyncio.run(main())
```

### 4. @asyncify Decorator

```python
from asyncify import asyncify

@asyncify(cpu_bound=False)
def read_file(path: str) -> str:
    with open(path) as f:
        return f.read()

async def main():
    content = await read_file("data.txt")
    print(content)

asyncio.run(main())
```

## Advanced Usage

### CPU-bound Task Marking

```python
# Option 1: Attribute (recommended)
def cpu_task(n: int) -> int:
    return sum(i * i for i in range(n))

cpu_task._cpu_bound = True
result = await run_sync(cpu_task, 1_000_000)

# Option 2: Decorator
@asyncify(cpu_bound=True)
def cpu_task(n: int) -> int:
    return sum(i * i for i in range(n))

result = await cpu_task(1_000_000)
```

### Concurrent Execution

```python
async def concurrent_example():
    tasks = [
        run_sync(io_task, url)
        for url in urls
    ]
    results = await asyncio.gather(*tasks)
```

## Performance

- **Thread Pool**: Adaptive sizing `max(32, CPU_COUNT * 4)` for high I/O concurrency
- **Process Pool**: CPU-count workers with adaptive throttling
- **Event-based dispatcher**: No busy polling, efficient task distribution
- **CPU monitoring**: Dynamic workload adjustment (requires `psutil`)

## Type Safety

```bash
uv run basedpyright
# 0 errors, 0 warnings, 0 notes
```

Full type hints with generics:
```python
from asyncify import run_sync

def typed_function(x: int) -> str:
    return str(x)

# Type checker knows result is str
result: str = await run_sync(typed_function, 42)
```
