"""Research Agent Page."""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure the project root (tradeMind/) is on sys.path so that `frontend`
# package imports work no matter the working directory Streamlit runs from.
_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import streamlit as st
import json

from frontend.services.api_client import get_api_client
from frontend.services.cache import cached_research, invalidate_research


def main():
    st.title("🔬 Research Agent")

    # Input controls
    col1, col2, col3, col4 = st.columns([2, 1, 1, 1])
    with col1:
        ticker = st.text_input("Ticker Symbol", value="MSFT", placeholder="e.g., MSFT, AAPL").upper()
    with col2:
        period = st.selectbox("Period", ["1mo", "3mo", "6mo", "1y", "2y"], index=2)
    with col3:
        interval = st.selectbox("Interval", ["1d", "1wk", "1mo"], index=0)
    with col4:
        if st.button("🔍 Analyze", type="primary", use_container_width=True):
            invalidate_research()
            st.rerun()

    if not ticker:
        st.warning("Enter a ticker symbol to run research.")
        return

    # Run research
    with st.spinner(f"Running research for {ticker}..."):
        try:
            report = cached_research(ticker, period, interval)
        except Exception as e:
            st.error(f"Research failed: {e}")
            return

    # Display report
    display_research_report(report)


def display_research_report(report: dict):
    """Display the research report in a structured format."""

    # Signal badge
    signal = report.get("signal", "UNKNOWN")
    signal_colors = {"BUY": "🟢", "SELL": "🔴", "HOLD": "🟡", "INSUFFICIENT_DATA": "⚪"}
    st.markdown(f"## {signal_colors.get(signal, '⚪')} Signal: **{signal}**")

    # Key metrics
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Ticker", report.get("ticker", "N/A"))
    m2.metric("Latest Price", f"${report.get('latest_price', 0):.2f}")
    m3.metric("Stop Loss", f"${report.get('proposed_stop_loss', 0):.2f}" if report.get("proposed_stop_loss") else "N/A")
    m4.metric("Take Profit", f"${report.get('proposed_take_profit', 0):.2f}" if report.get("proposed_take_profit") else "N/A")

    # Interpretation
    if report.get("interpretation"):
        st.subheader("📝 Analysis")
        st.info(report["interpretation"])
        st.caption(f"Source: {report.get('interpretation_source', 'unknown')}")

    # Strategy breakdown
    decision = report.get("decision", {})
    strategies = decision.get("strategies", [])

    if strategies:
        st.subheader("📊 Strategy Votes")
        st.markdown(f"""
        **Consensus**: {decision.get('buy_votes', 0)} BUY | {decision.get('sell_votes', 0)} SELL | {decision.get('hold_votes', 0)} HOLD
        """)

        for strat in strategies:
            with st.expander(f"{strat.get('strategy', 'Unknown')} → **{strat.get('signal', 'UNKNOWN')}**"):
                evidence = strat.get("evidence", [])
                if evidence:
                    for ev in evidence:
                        st.write(f"• {ev}")
                else:
                    st.write("No evidence provided")

    # Limitations
    limitations = report.get("limitations", [])
    if limitations:
        st.subheader("⚠️ Limitations")
        for lim in limitations:
            st.warning(lim)

    # Data issues
    issues = report.get("data_issues", [])
    if issues:
        st.subheader("🔧 Data Issues")
        for issue in issues:
            st.error(f"{issue.get('type', 'Unknown')}: {issue.get('message', 'No message')}")

    # Raw JSON
    with st.expander("🔧 Raw Report (JSON)"):
        st.json(report)


if __name__ == "__main__":
    main()