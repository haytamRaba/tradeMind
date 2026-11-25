"""Order History & Performance Page."""

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
import plotly.graph_objects as go

from frontend.services.api_client import get_api_client
from frontend.services.cache import cached_orders, invalidate_orders
from frontend.components.charts import create_equity_curve, create_pnl_chart


def main():
    st.title("📜 Order History & Performance")

    # Refresh
    if st.button("🔄 Refresh History", use_container_width=True):
        invalidate_orders()
        st.rerun()

    # Load orders
    with st.spinner("Loading history..."):
        try:
            orders = cached_orders(200)
        except Exception as e:
            st.error(f"Failed to load history: {e}")
            return

    if not orders:
        st.info("No order history yet. Execute some trades to see history.")
        return

    # Convert to DataFrame
    df = pd.DataFrame(orders)
    df["created_at"] = pd.to_datetime(df["created_at"])
    df = df.sort_values("created_at")

    # Filters
    st.subheader("🔍 Filters")
    col1, col2, col3 = st.columns(3)
    with col1:
        tickers = ["All"] + sorted(df["ticker"].unique().tolist())
        selected_ticker = st.selectbox("Ticker", tickers)
    with col2:
        statuses = ["All"] + sorted(df["status"].unique().tolist())
        selected_status = st.selectbox("Status", statuses)
    with col3:
        sides = ["All"] + sorted(df["side"].unique().tolist())
        selected_side = st.selectbox("Side", sides)

    # Apply filters
    filtered_df = df.copy()
    if selected_ticker != "All":
        filtered_df = filtered_df[filtered_df["ticker"] == selected_ticker]
    if selected_status != "All":
        filtered_df = filtered_df[filtered_df["status"] == selected_status]
    if selected_side != "All":
        filtered_df = filtered_df[filtered_df["side"] == selected_side]

    # Summary stats
    filled_orders = filtered_df[filtered_df["status"] == "FILLED"]
    if not filled_orders.empty:
        total_trades = len(filled_orders)
        buys = filled_orders[filled_orders["side"] == "BUY"]
        sells = filled_orders[filled_orders["side"] == "SELL"]
        total_pnl = filled_orders["realized_pnl"].sum()
        win_trades = filled_orders[filled_orders["realized_pnl"] > 0]
        loss_trades = filled_orders[filled_orders["realized_pnl"] < 0]
        win_rate = len(win_trades) / total_trades * 100 if total_trades > 0 else 0
        avg_win = win_trades["realized_pnl"].mean() if len(win_trades) > 0 else 0
        avg_loss = loss_trades["realized_pnl"].mean() if len(loss_trades) > 0 else 0

        st.subheader("📊 Performance Summary")
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Total Trades", total_trades)
        m2.metric("Win Rate", f"{win_rate:.1f}%")
        m3.metric("Total Realized P&L", f"${total_pnl:,.2f}")
        m4.metric("Avg Win / Avg Loss", f"${avg_win:,.2f} / ${avg_loss:,.2f}")

        m5, m6, m7 = st.columns(3)
        m5.metric("Gross Profit", f"${win_trades['realized_pnl'].sum():,.2f}")
        m6.metric("Gross Loss", f"${loss_trades['realized_pnl'].sum():,.2f}")
        profit_factor = abs(win_trades["realized_pnl"].sum() / loss_trades["realized_pnl"].sum()) if loss_trades["realized_pnl"].sum() != 0 else float('inf')
        m7.metric("Profit Factor", f"{profit_factor:.2f}" if profit_factor != float('inf') else "∞")

    # P&L Chart
    if not filled_orders.empty:
        st.subheader("📈 Realized P&L by Trade")
        pnl_data = filled_orders[["ticker", "realized_pnl", "created_at"]].copy()
        pnl_data["trade_num"] = range(1, len(pnl_data) + 1)

        fig = go.Figure()
        colors = ["green" if p >= 0 else "red" for p in pnl_data["realized_pnl"]]
        fig.add_trace(go.Bar(
            x=pnl_data["trade_num"],
            y=pnl_data["realized_pnl"],
            marker_color=colors,
            text=pnl_data["ticker"],
            textposition="outside",
            name="Realized P&L",
        ))
        fig.add_trace(go.Scatter(
            x=pnl_data["trade_num"],
            y=pnl_data["realized_pnl"].cumsum(),
            mode="lines+markers",
            name="Cumulative P&L",
            line=dict(color="blue", width=2),
            yaxis="y2",
        ))
        fig.update_layout(
            height=400,
            template="plotly_white",
            title="Trade P&L & Cumulative Performance",
            xaxis_title="Trade #",
            yaxis_title="P&L ($)",
            yaxis2=dict(title="Cumulative ($)", overlaying="y", side="right"),
            showlegend=True,
        )
        st.plotly_chart(fig, use_container_width=True)

    # Order table
    st.subheader("📋 Order Details")
    display_df = filtered_df.copy()
    display_df["created_at"] = display_df["created_at"].dt.strftime("%Y-%m-%d %H:%M:%S")
    display_df["execution_price"] = display_df["execution_price"].round(4)
    display_df["quantity"] = display_df["quantity"].round(4)
    display_df["realized_pnl"] = display_df["realized_pnl"].round(2)

    st.dataframe(
        display_df[[
            "order_id", "ticker", "side", "status", "quantity",
            "execution_price", "stop_loss", "take_profit",
            "realized_pnl", "idempotency_key", "message", "replayed", "created_at"
        ]],
        use_container_width=True,
        hide_index=True,
        column_config={
            "order_id": "ID",
            "ticker": "Ticker",
            "side": "Side",
            "status": "Status",
            "quantity": "Qty",
            "execution_price": "Price",
            "stop_loss": "Stop",
            "take_profit": "Target",
            "realized_pnl": "P&L",
            "idempotency_key": "Idempotency Key",
            "message": "Message",
            "replayed": "Replayed",
            "created_at": "Created At",
        },
    )

    # Export
    st.divider()
    col1, col2 = st.columns(2)
    with col1:
        csv = filtered_df.to_csv(index=False)
        st.download_button(
            "📥 Download CSV",
            csv,
            file_name=f"trademind_history_{pd.Timestamp.now().strftime('%Y%m%d')}.csv",
            mime="text/csv",
            use_container_width=True,
        )
    with col2:
        if st.button("🗑️ Clear History (Dev Only)", use_container_width=True):
            st.warning("This would clear the database - not implemented in demo")


if __name__ == "__main__":
    main()