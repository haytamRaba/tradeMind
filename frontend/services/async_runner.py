"""Async runner utility for Streamlit - ensures single event loop per operation."""

from __future__ import annotations

import asyncio
from typing import Callable, Awaitable, TypeVar

from frontend.services.api_client import _run_with_client

T = TypeVar("T")


def run_async(coro_factory: Callable[[], Awaitable[T]], api_key: str | None = None) -> T:
    """
    Run an async operation with a fresh client that gets closed.

    Usage:
        result = run_async(lambda c: c.some_method())
    """
    return asyncio.run(_run_with_client(api_key, coro_factory))