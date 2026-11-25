"""Paper Trading Dashboard Page."""

from __future__ import annotations

import streamlit as st
import pandas as pd

from frontend.services.api_client import get_api_client
from frontend.services.cache import cached_portfolio, cached_orders, invalidate_portfolio, invalidate_orders
from frontend.components.charts import create_equity_curve, create_pnl_chart


def main():
    st.title("📈 Paper Trading Dashboard")

    # Refresh button
    col1, col2, col3 = st.columns([1, 1, 4])
    with col1:
        if st.button("🔄 Refresh Portfolio", use_container_width=True):
            invalidate_portfolio()
            invalidate_orders()
            st.rerun()
    with col2:
        if st.button("🔍 Monitor Stops", use_container_width=True):
            monitor_positions()

    # Load portfolio
    with st.spinner("Loading portfolio..."):
        try:
            portfolio = cached_portfolio()
            orders = cached_orders(50)
        except Exception as e:
            st.error(f"Failed to load data: {e}")
            return

    # Portfolio overview
    st.subheader("💼 Portfolio Overview")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Equity", f"${portfolio.get('equity', 0):,.2f}")
    m2.metric("Cash", f"${portfolio.get('cash', 0):,.2f}")
    m3.metric("Market Exposure", f"${portfolio.get('market_exposure', 0):,.2f}")
    m4.metric("Unrealized P&L", f"${portfolio.get('unrealized_pnl', 0):,.2f}")

    m5, m6, m7 = st.columns(3)
    m5.metric("Realized P&L (Today)", f"${portfolio.get('realized_pnl_today', 0):,.2f}")
    m6.metric("Starting Cash", f"${portfolio.get('starting_cash', 0):,.2f}")
    m7.metric("Positions", len(portfolio.get('positions', [])))

    # Positions table
    positions = portfolio.get("positions", [])
    if positions:
        st.subheader("📦 Open Positions")
        pos_df = pd.DataFrame(positions)
        pos_df["unrealized_pnl_pct"] = ((pos_df["latest_price"] - pos_df["average_entry_price"]) / pos_df["average_entry_price"] * 100).round(2)
        pos_df["market_value"] = pos_df["market_value"].round(2)
        pos_df["unrealized_pnl"] = pos_df["unrealized_pnl"].round(2)

        # Format for display
        display_cols = ["ticker", "quantity", "average_entry_price", "latest_price", "market_value", "unrealized_pnl", "unrealized_pnl_pct", "stop_loss", "take_profit"]
        st.dataframe(
            pos_df[display_cols].style.format({
                "average_entry_price": "${:.2f}",
                "latest_price": "${:.2f}",
                "market_value": "${:,.2f}",
                "unrealized_pnl": "${:,.2f}",
                "unrealized_pnl_pct": "{:+.2f}%",
                "stop_loss": "${:.2f}",
                "take_profit": "${:.2f}",
            }).applymap(lambda v: "color: green" if isinstance(v, (int, float)) and v > 0 else ("color: red" if isinstance(v, (int, float)) and v < 0 else ""), subset=["unrealized_pnl", "unrealized_pnl_pct"]),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("No open positions")

    # Execute trade section
    st.divider()
    st.subheader("🎯 Execute Trade")
    with st.form("execute_trade"):
        col1, col2, col3 = st.columns(3)
        with col1:
            trade_ticker = st.text_input("Ticker", placeholder="MSFT").upper()
        with col2:
            idempotency_key = st.text_input("Idempotency Key", placeholder="trade-msft-20240115")
        with col3:
            st.write("")  # spacer
            submit = st.form_submit_button("Execute Trade", type="primary", use_container_width=True)

        if submit and trade_ticker and idempotency_key:
            execute_trade(trade_ticker, idempotency_key)

    # Order history
    st.divider()
    st.subheader("📜 Order History")
    if orders:
        orders_df = pd.DataFrame(orders)
        orders_df["created_at"] = pd.to_datetime(orders_df["created_at"]).dt.strftime("%Y-%m-%d %H:%M:%S")
        st.dataframe(
            orders_df[["order_id", "ticker", "side", "status", "quantity", "execution_price", "stop_loss", "take_profit", "realized_pnl", "created_at"]],
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("No orders yet")


def execute_trade(ticker: str, idempotency_key: str):
    """Execute a paper trade."""
    from frontend.services.async_runner import run_async

    try:
        with st.spinner(f"Executing trade for {ticker}..."):
            result = run_async(lambda c: c.execute_trade(ticker, idempotency_key))
        st.success(f"Trade executed: {result.get('execution', {}).get('status', 'Unknown')}")
        st.json(result)
        invalidate_portfolio()
        invalidate_orders()
        st.rerun()
    except Exception as e:
        st.error(f"Trade failed: {e}")


def monitor_positions():
    """Monitor protective stops."""
    from frontend.services.async_runner import run_async

    try:
        with st.spinner("Monitoring positions..."):
            result = run_async(lambda c: c.monitor_positions())
        st.success(f"Monitoring complete: {len(result.get('exits', []))} exits triggered")
        if result.get("exits"):
            for exit in result["exits"]:
                st.info(f"Exit: {exit.get('ticker')} - {exit.get('message')}")
        invalidate_portfolio()
        invalidate_orders()
        st.rerun()
    except Exception as e:
        st.error(f"Monitor failed: {e}")


if __name__ == "__main__":
    main()