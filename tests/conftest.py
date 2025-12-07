"""Pytest configuration for asyncify tests."""

import os

import pytest


@pytest.fixture(scope='session', autouse=True)
def cleanup_pools():
    """Force fast exit after tests to avoid ProcessPoolExecutor atexit hang."""
    yield
    # ProcessPoolExecutor регистрирует atexit handler с blocking join()
    # который зависает на 30+ секунд. os._exit(0) обходит все atexit handlers.
    os._exit(0)
