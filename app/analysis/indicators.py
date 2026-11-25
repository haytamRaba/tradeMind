"""Deterministic technical indicators calculated from validated OHLCV bars."""

from __future__ import annotations

from math import sqrt
from typing import Any

import pandas as pd


def calculate_indicators(history: pd.DataFrame) -> dict[str, float | None]:
    """Calculate the indicators used by the initial research strategies."""
    required = {"high", "low", "close"}
    missing = required.difference(history.columns)
    if missing:
        raise ValueError(f"History is missing columns: {', '.join(sorted(missing))}")
    if history.empty:
        return {name: None for name in _INDICATOR_NAMES}

    close = pd.to_numeric(history["close"], errors="raise").astype(float)
    high = pd.to_numeric(history["high"], errors="raise").astype(float)
    low = pd.to_numeric(history["low"], errors="raise").astype(float)
    sma_20 = close.rolling(20, min_periods=20).mean()
    sma_50 = close.rolling(50, min_periods=50).mean()
    ema_12 = close.ewm(span=12, adjust=False, min_periods=12).mean()
    ema_26 = close.ewm(span=26, adjust=False, min_periods=26).mean()
    macd = ema_12 - ema_26
    macd_signal = macd.ewm(span=9, adjust=False, min_periods=9).mean()

    changes = close.diff()
    gains = changes.clip(lower=0)
    losses = -changes.clip(upper=0)
    average_gain = gains.ewm(alpha=1 / 14, adjust=False, min_periods=14).mean()
    average_loss = losses.ewm(alpha=1 / 14, adjust=False, min_periods=14).mean()
    relative_strength = average_gain / average_loss.replace(0, float("nan"))
    rsi = 100 - (100 / (1 + relative_strength))
    rsi = rsi.mask((average_loss == 0) & (average_gain > 0), 100)
    rsi = rsi.mask((average_loss == 0) & (average_gain == 0), 50)

    true_range = pd.concat(
        [high - low, (high - close.shift()).abs(), (low - close.shift()).abs()],
        axis=1,
    ).max(axis=1)
    atr_14 = true_range.rolling(14, min_periods=14).mean()
    bollinger_mid = sma_20
    bollinger_width = close.rolling(20, min_periods=20).std(ddof=0) * 2
    daily_returns = close.pct_change(fill_method=None)
    volatility = daily_returns.rolling(20, min_periods=20).std(ddof=1) * sqrt(252)

    return {
        "sma_20": _latest(sma_20),
        "sma_50": _latest(sma_50),
        "ema_12": _latest(ema_12),
        "ema_26": _latest(ema_26),
        "rsi_14": _latest(rsi),
        "macd": _latest(macd),
        "macd_signal": _latest(macd_signal),
        "bollinger_upper": _latest(bollinger_mid + bollinger_width),
        "bollinger_lower": _latest(bollinger_mid - bollinger_width),
        "atr_14": _latest(atr_14),
        "historical_volatility_20": _latest(volatility),
    }


_INDICATOR_NAMES = (
    "sma_20",
    "sma_50",
    "ema_12",
    "ema_26",
    "rsi_14",
    "macd",
    "macd_signal",
    "bollinger_upper",
    "bollinger_lower",
    "atr_14",
    "historical_volatility_20",
)


def _latest(series: pd.Series) -> float | None:
    value: Any = series.iloc[-1]
    if pd.isna(value):
        return None
    return float(value)
