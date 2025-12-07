"""Pytest configuration for asyncify tests."""

import os

import pytest


@pytest.fixture(scope="session", autouse=True)
def cleanup_pools():
    """Force fast exit after tests to avoid ProcessPoolExecutor atexit hang."""
    yield
    os._exit(0)
