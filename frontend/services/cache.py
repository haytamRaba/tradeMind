"""Streamlit caching wrappers for API calls."""

from __future__ import annotations

import streamlit as st

from frontend.services.async_runner import run_async


@st.cache_data(ttl=60)
def cached_market_data(ticker: str, period: str, interval: str) -> dict:
    """Cache market data fetch."""
    return run_async(lambda c: c.get_market_data(ticker, period, interval))


@st.cache_data(ttl=120)
def cached_research(ticker: str, period: str, interval: str) -> dict:
    """Cache research agent result."""
    return run_async(lambda c: c.run_research(ticker, period, interval))


@st.cache_data(ttl=30)
def cached_portfolio() -> dict:
    """Cache portfolio state."""
    return run_async(lambda c: c.get_portfolio())


@st.cache_data(ttl=30)
def cached_orders(limit: int = 100) -> list:
    """Cache order history."""
    return run_async(lambda c: c.get_orders(limit))


def clear_all_caches():
    """Clear all cached data."""
    st.cache_data.clear()


def invalidate_market_data():
    """Invalidate market data cache."""
    cached_market_data.clear()


def invalidate_research():
    """Invalidate research cache."""
    cached_research.clear()


def invalidate_portfolio():
    """Invalidate portfolio cache."""
    cached_portfolio.clear()


def invalidate_orders():
    """Invalidate orders cache."""
    cached_orders.clear()