"""Risk Monitor Page."""

from __future__ import annotations

import streamlit as st
import pandas as pd

from frontend.services.api_client import get_api_client
from frontend.services.cache import cached_portfolio, invalidate_portfolio


def main():
    st.title("⚠️ Risk Monitor")

    # Refresh
    if st.button("🔄 Refresh Risk Data", use_container_width=True):
        invalidate_portfolio()
        st.rerun()

    # Load portfolio
    with st.spinner("Loading risk data..."):
        try:
            portfolio = cached_portfolio()
        except Exception as e:
            st.error(f"Failed to load data: {e}")
            return

    # Risk limits (from settings)
    st.subheader("📏 Risk Limits")
    limits = {
        "Max Risk per Trade": "1.00%",
        "Max Position Size": "10.00%",
        "Max Portfolio Exposure": "50.00%",
        "Max Daily Loss": "5.00%",
        "Max Open Positions": "10",
    }

    col1, col2 = st.columns(2)
    for i, (name, value) in enumerate(limits.items()):
        with col1 if i % 2 == 0 else col2:
            st.metric(name, value)

    # Current risk metrics
    st.divider()
    st.subheader("📊 Current Risk Metrics")

    equity = portfolio.get("equity", 0)
    cash = portfolio.get("cash", 0)
    exposure = portfolio.get("market_exposure", 0)
    positions = portfolio.get("positions", [])
    realized_today = portfolio.get("realized_pnl_today", 0)

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Portfolio Exposure", f"{exposure/equity*100:.2f}%" if equity > 0 else "0%", delta=f"Limit: 50%")
    m2.metric("Open Positions", len(positions), delta=f"Limit: 10")
    m3.metric("Daily P&L", f"${realized_today:,.2f}", delta=f"Limit: -${equity*0.05:,.2f}")
    m4.metric("Available Cash", f"${cash:,.2f}", delta=f"{(cash/equity)*100:.1f}% of equity" if equity > 0 else "N/A")

    # Exposure bar
    st.progress(min(exposure / (equity * 0.5), 1.0) if equity > 0 else 0, text=f"Portfolio Exposure: {exposure/equity*100:.1f}% / 50%")

    # Position sizing calculator
    st.divider()
    st.subheader("🧮 Position Size Calculator")

    with st.form("position_sizer"):
        col1, col2, col3 = st.columns(3)
        with col1:
            entry_price = st.number_input("Entry Price ($)", min_value=0.01, value=100.0, step=0.01)
            stop_loss = st.number_input("Stop Loss ($)", min_value=0.01, value=95.0, step=0.01)
        with col2:
            risk_pct = st.number_input("Risk per Trade (%)", min_value=0.1, max_value=10.0, value=1.0, step=0.1)
            max_pos_pct = st.number_input("Max Position (%)", min_value=1.0, max_value=50.0, value=10.0, step=1.0)
        with col3:
            max_port_pct = st.number_input("Max Portfolio (%)", min_value=10.0, max_value=100.0, value=50.0, step=5.0)
            current_positions = st.number_input("Current Positions", min_value=0, max_value=20, value=len(positions))

        submitted = st.form_submit_button("Calculate Size", type="primary")

        if submitted:
            if stop_loss >= entry_price:
                st.error("Stop loss must be below entry price for BUY orders")
            else:
                calculate_position_size(
                    equity=equity,
                    cash=cash,
                    entry_price=entry_price,
                    stop_loss=stop_loss,
                    risk_pct=risk_pct / 100,
                    max_pos_pct=max_pos_pct / 100,
                    max_port_pct=max_port_pct / 100,
                    current_positions=current_positions,
                    current_exposure=exposure,
                )

    # Position risk breakdown
    if positions:
        st.divider()
        st.subheader("📦 Position Risk Breakdown")

        for pos in positions:
            with st.expander(f"{pos['ticker']} - {pos['quantity']} shares"):
                entry = pos["average_entry_price"]
                current = pos["latest_price"]
                stop = pos["stop_loss"]
                target = pos["take_profit"]
                qty = pos["quantity"]

                unrealized = (current - entry) * qty
                unrealized_pct = (current - entry) / entry * 100
                risk_per_share = entry - stop
                total_risk = risk_per_share * qty
                risk_pct_of_equity = total_risk / equity * 100 if equity > 0 else 0

                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Entry", f"${entry:.2f}")
                c2.metric("Current", f"${current:.2f}", f"{unrealized_pct:+.2f}%")
                c3.metric("Stop Loss", f"${stop:.2f}", f"Risk/share: ${risk_per_share:.2f}")
                c4.metric("Take Profit", f"${target:.2f}" if target else "N/A")

                c5, c6, c7 = st.columns(3)
                c5.metric("Position Value", f"${pos['market_value']:,.2f}")
                c6.metric("Total Risk", f"${total_risk:,.2f}", f"{risk_pct_of_equity:.2f}% of equity")
                c7.metric("Unrealized P&L", f"${unrealized:,.2f}")


def calculate_position_size(
    equity: float,
    cash: float,
    entry_price: float,
    stop_loss: float,
    risk_pct: float,
    max_pos_pct: float,
    max_port_pct: float,
    current_positions: int,
    current_exposure: float,
):
    """Calculate position size based on risk parameters."""
    from decimal import Decimal, ROUND_FLOOR

    equity_d = Decimal(str(equity))
    cash_d = Decimal(str(cash))
    entry_d = Decimal(str(entry_price))
    stop_d = Decimal(str(stop_loss))
    risk_pct_d = Decimal(str(risk_pct))
    max_pos_pct_d = Decimal(str(max_pos_pct))
    max_port_pct_d = Decimal(str(max_port_pct))
    exposure_d = Decimal(str(current_exposure))

    if entry_d <= 0 or stop_d <= 0 or stop_d >= entry_d:
        st.error("Invalid prices: stop loss must be positive and below entry")
        return

    risk_per_share = entry_d - stop_d
    risk_budget = equity_d * risk_pct_d
    position_capacity = max(Decimal("0"), equity_d * max_pos_pct_d - Decimal("0"))
    portfolio_capacity = max(Decimal("0"), equity_d * max_port_pct_d - exposure_d)
    maximum_value = min(
        risk_budget / risk_per_share * entry_d,
        position_capacity,
        portfolio_capacity,
        cash_d,
    )
    shares = (maximum_value / entry_d).to_integral_value(rounding=ROUND_FLOOR)
    shares = max(Decimal("0"), shares)

    # Results
    st.success("✅ Calculation Complete")
    r1, r2, r3, r4 = st.columns(4)
    r1.metric("Shares", int(shares))
    r2.metric("Position Value", f"${float(shares * entry_d):,.2f}")
    r3.metric("Risk Amount", f"${float(shares * risk_per_share):,.2f}")
    r4.metric("Cash After", f"${float(cash_d - shares * entry_d):,.2f}")

    # Warnings
    if shares == 0:
        st.warning("⚠️ Position size is 0 - check risk limits or available cash")
    if current_positions >= 10:
        st.warning("⚠️ Maximum open positions (10) reached")
    if current_exposure / equity > max_port_pct if equity > 0 else False:
        st.warning("⚠️ Portfolio exposure limit reached")


if __name__ == "__main__":
    main()