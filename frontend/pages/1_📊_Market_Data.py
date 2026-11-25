"""Market Data Explorer Page."""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure the project root (tradeMind/) is on sys.path so that `frontend`
# package imports work no matter the working directory Streamlit runs from.
_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import streamlit as st
import pandas as pd

from frontend.services.api_client import get_api_client
from frontend.services.cache import cached_market_data, invalidate_market_data
from frontend.components.charts import create_candlestick_chart


def main():
    st.title("📊 Market Data Explorer")

    # Ticker input
    col1, col2, col3, col4 = st.columns([2, 1, 1, 1])
    with col1:
        ticker = st.text_input("Ticker Symbol", value="MSFT", placeholder="e.g., MSFT, AAPL, GOOGL").upper()
    with col2:
        period = st.selectbox("Period", ["1d", "5d", "1mo", "3mo", "6mo", "1y", "2y", "5y", "10y", "ytd", "max"], index=2)
    with col3:
        interval = st.selectbox("Interval", ["1m", "2m", "5m", "15m", "30m", "60m", "90m", "1h", "1d", "5d", "1wk", "1mo", "3mo"], index=8)
    with col4:
        if st.button("🔄 Fetch", type="primary", use_container_width=True):
            invalidate_market_data()
            st.rerun()

    if not ticker:
        st.warning("Enter a ticker symbol to fetch market data.")
        return

    # Fetch data
    with st.spinner(f"Fetching {ticker} data..."):
        try:
            data = cached_market_data(ticker, period, interval)
        except Exception as e:
            st.error(f"Failed to fetch data: {e}")
            return

    if not data or not data.get("data"):
        st.warning(f"No data returned for {ticker}")
        return

    bars = data["data"]
    indicators = data.get("indicators", {})

    # Summary metrics
    if bars:
        latest = bars[-1]
        first = bars[0]
        change = latest["close"] - first["close"]
        change_pct = (change / first["close"]) * 100

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Latest Close", f"${latest['close']:.2f}", f"{change:+.2f} ({change_pct:+.2f}%)")
        m2.metric("Period High", f"${max(b['high'] for b in bars):.2f}")
        m3.metric("Period Low", f"${min(b['low'] for b in bars):.2f}")
        m4.metric("Avg Volume", f"{sum(b['volume'] for b in bars) / len(bars):,.0f}")

    # Chart
    st.plotly_chart(
        create_candlestick_chart(bars, indicators, title=f"{ticker} - {period} ({interval})"),
        use_container_width=True,
    )

    # Indicators display
    if indicators:
        st.subheader("📈 Technical Indicators")
        ind_cols = st.columns(4)
        for i, (name, value) in enumerate(indicators.items()):
            if value is not None:
                with ind_cols[i % 4]:
                    st.metric(name.upper(), f"{value:.4f}")

    # Data table
    with st.expander("📋 Raw Data (last 20 bars)"):
        df = pd.DataFrame(bars[-20:])
        df["timestamp"] = pd.to_datetime(df["timestamp"]).dt.strftime("%Y-%m-%d %H:%M")
        st.dataframe(df, use_container_width=True, hide_index=True)


if __name__ == "__main__":
    main()