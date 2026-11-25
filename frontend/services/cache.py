"""Streamlit caching wrappers for API calls."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import streamlit as st

from frontend.services.async_runner import run_async

_PORTFOLIO_NUMERIC_FIELDS = (
    "starting_cash",
    "cash",
    "equity",
    "market_exposure",
    "unrealized_pnl",
    "realized_pnl_today",
)

_POSITION_NUMERIC_FIELDS = (
    "quantity",
    "average_entry_price",
    "stop_loss",
    "take_profit",
    "latest_price",
    "market_value",
    "unrealized_pnl",
)

_ORDER_NUMERIC_FIELDS = (
    "quantity",
    "execution_price",
    "stop_loss",
    "take_profit",
    "realized_pnl",
    "cash_after",
)


def _to_float(value: Any, default: float = 0.0) -> float:
    """Convert a JSON-decoded value (Decimal / str / int / float / None) to float.

    The FastAPI backend serializes ``Decimal`` fields as JSON strings, so the
    frontend must coerce them back to numbers before formatting/comparing them.
    """
    if value is None:
        return default
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, (int, float, Decimal)):
        return float(value)
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _clean_numeric(obj: dict, fields: tuple[str, ...]) -> dict:
    """Return a copy of ``obj`` with the given numeric fields coerced to float."""
    cleaned = dict(obj)
    for field in fields:
        if field in cleaned:
            cleaned[field] = _to_float(cleaned.get(field))
    return cleaned


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
    """Cache portfolio state with numeric fields coerced to float."""
    data = run_async(lambda c: c.get_portfolio()) or {}
    data = _clean_numeric(data, _PORTFOLIO_NUMERIC_FIELDS)
    positions = data.get("positions", [])
    if isinstance(positions, list):
        data["positions"] = [
            _clean_numeric(pos, _POSITION_NUMERIC_FIELDS) if isinstance(pos, dict) else pos
            for pos in positions
        ]
    return data


@st.cache_data(ttl=30)
def cached_orders(limit: int = 100) -> list:
    """Cache order history with numeric fields coerced to float."""
    data = run_async(lambda c: c.get_orders(limit)) or []
    if not isinstance(data, list):
        return []
    return [
        _clean_numeric(order, _ORDER_NUMERIC_FIELDS) if isinstance(order, dict) else order
        for order in data
    ]


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