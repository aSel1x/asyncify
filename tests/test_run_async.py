"""Tests for run_async function."""

import asyncio

from asyncify import run_async


async def async_add(x: int, y: int) -> int:
    """Simple async addition."""
    await asyncio.sleep(0.01)
    return x + y


async def async_multiply(x: int, y: int) -> int:
    """Async multiplication."""
    return x * y


async def async_with_error(fail: bool) -> str:
    """Async function that can fail."""
    await asyncio.sleep(0.01)
    if fail:
        raise ValueError("Intentional error")
    return "success"


def test_run_async_basic():
    """Test basic run_async call."""
    result = run_async(async_add, 2, 3)
    assert result == 5


def test_run_async_kwargs():
    """Test run_async with keyword arguments."""
    result = run_async(async_add, x=10, y=20)
    assert result == 30


def test_run_async_no_args():
    """Test run_async with no arguments."""

    async def get_value() -> int:
        return 42

    result = run_async(get_value)
    assert result == 42


def test_run_async_exception():
    """Test that exceptions are properly propagated."""
    try:
        _ = run_async(async_with_error, fail=True)
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert str(e) == "Intentional error"


def test_run_async_success():
    """Test successful async execution."""
    result = run_async(async_with_error, fail=False)
    assert result == "success"
