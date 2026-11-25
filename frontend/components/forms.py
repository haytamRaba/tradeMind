"""Reusable form components for Streamlit frontend.

This module provides reusable form components used across the Streamlit dashboard pages:
- 1_📊_Market_Data.py: Uses period_interval_selector, indicator_overlay_form
- 2_🔬_Research.py: Uses research_run_form
- 3_📈_Trading.py: Uses trade_execution_form
- 4_⚠️_Risk.py: Uses position_size_form
- 5_📜_History.py: Uses export_form
- app.py: Uses api_config_form in sidebar

No existing file provides these reusable form components - they were previously inline in each page.
Data schemas: Reads/writes Streamlit session state, form inputs as strings/numbers.
User instruction: Build Streamlit frontend per plan.md step by step.
"""

from __future__ import annotations

import streamlit as st
import pandas as pd
from typing import Any, Callable


def ticker_search_form(
    label: str = "Ticker Symbol",
    placeholder: str = "MSFT",
    key: str = "ticker_search",
    on_submit: Callable[[str], Any] | None = None,
) -> str:
    """Ticker search input with submit button."""
    col1, col2 = st.columns([3, 1])
    with col1:
        ticker = st.text_input(
            label,
            placeholder=placeholder,
            key=key,
            label_visibility="collapsed",
        ).upper()
    with col2:
        submitted = st.form_submit_button("🔍 Search", use_container_width=True)

    if submitted and ticker and on_submit:
        on_submit(ticker)

    return ticker


def period_interval_selector(
    key: str = "period_interval",
    default_period: str = "1mo",
    default_interval: str = "1d",
) -> tuple[str, str]:
    """Period and interval selector for market data."""
    col1, col2 = st.columns(2)
    with col1:
        period = st.selectbox(
            "Period",
            ["1d", "5d", "1mo", "3mo", "6mo", "1y", "2y", "5y", "10y", "ytd", "max"],
            index=2,
            key=f"{key}_period",
        )
    with col2:
        interval = st.selectbox(
            "Interval",
            ["1m", "2m", "5m", "15m", "30m", "60m", "90m", "1h", "1d", "5d", "1wk", "1mo", "3mo"],
            index=8,
            key=f"{key}_interval",
        )
    return period, interval


def trade_execution_form(
    key: str = "trade_execution",
    on_submit: Callable[[str, str], Any] | None = None,
) -> tuple[str, str]:
    """Trade execution form with ticker and idempotency key."""
    with st.form(key):
        col1, col2 = st.columns(2)
        with col1:
            ticker = st.text_input(
                "Ticker",
                placeholder="MSFT",
                key=f"{key}_ticker",
            ).upper()
        with col2:
            idempotency_key = st.text_input(
                "Idempotency Key",
                placeholder="trade-msft-20240115",
                key=f"{key}_idem",
                help="Unique key for safe retry (max 64 chars)",
            )

        submitted = st.form_submit_button(
            "Execute Trade",
            type="primary",
            use_container_width=True,
        )

        if submitted and ticker and idempotency_key and on_submit:
            on_submit(ticker, idempotency_key)

    return ticker, idempotency_key


def research_run_form(
    key: str = "research_run",
    on_submit: Callable[[str], Any] | None = None,
) -> str:
    """Research agent execution form."""
    with st.form(key):
        ticker = st.text_input(
            "Ticker",
            placeholder="MSFT",
            key=f"{key}_ticker",
        ).upper()

        submitted = st.form_submit_button(
            "🔬 Run Research",
            type="primary",
            use_container_width=True,
        )

        if submitted and ticker and on_submit:
            on_submit(ticker)

    return ticker


def position_size_form(
    key: str = "position_size",
    default_entry: float = 100.0,
    default_stop: float = 95.0,
    on_submit: Callable[[dict], Any] | None = None,
) -> dict | None:
    """Position sizing calculator form."""
    with st.form(key):
        st.subheader("Position Size Calculator")

        col1, col2, col3 = st.columns(3)
        with col1:
            entry_price = st.number_input(
                "Entry Price ($)",
                min_value=0.01,
                value=default_entry,
                step=0.01,
                key=f"{key}_entry",
            )
            stop_loss = st.number_input(
                "Stop Loss ($)",
                min_value=0.01,
                value=default_stop,
                step=0.01,
                key=f"{key}_stop",
            )
        with col2:
            risk_pct = st.number_input(
                "Risk per Trade (%)",
                min_value=0.1,
                max_value=10.0,
                value=1.0,
                step=0.1,
                key=f"{key}_risk",
            )
            max_pos_pct = st.number_input(
                "Max Position (%)",
                min_value=1.0,
                max_value=50.0,
                value=10.0,
                step=1.0,
                key=f"{key}_max_pos",
            )
        with col3:
            max_port_pct = st.number_input(
                "Max Portfolio (%)",
                min_value=10.0,
                max_value=100.0,
                value=50.0,
                step=5.0,
                key=f"{key}_max_port",
            )
            current_positions = st.number_input(
                "Current Positions",
                min_value=0,
                max_value=20,
                value=0,
                key=f"{key}_curr_pos",
            )

        submitted = st.form_submit_button(
            "Calculate Size",
            type="primary",
            use_container_width=True,
        )

        if submitted and on_submit:
            params = {
                "entry_price": entry_price,
                "stop_loss": stop_loss,
                "risk_pct": risk_pct / 100,
                "max_pos_pct": max_pos_pct / 100,
                "max_port_pct": max_port_pct / 100,
                "current_positions": current_positions,
            }
            on_submit(params)
            return params

    return None


def api_config_form(
    key: str = "api_config",
    default_url: str = "http://localhost:8000",
    default_key: str = "",
    on_submit: Callable[[str, str], Any] | None = None,
) -> tuple[str, str]:
    """API configuration form for sidebar."""
    with st.form(key):
        st.subheader("API Configuration")

        api_url = st.text_input(
            "FastAPI Base URL",
            value=default_url,
            key=f"{key}_url",
            help="Base URL of the TradeMind FastAPI server",
        )

        api_key = st.text_input(
            "API Key",
            value=default_key,
            type="password",
            key=f"{key}_key",
            help="Optional API key for authenticated endpoints",
        )

        col1, col2 = st.columns(2)
        with col1:
            test_conn = st.form_submit_button(
                "🔗 Test Connection",
                use_container_width=True,
            )
        with col2:
            save = st.form_submit_button(
                "💾 Save",
                type="primary",
                use_container_width=True,
            )

        if test_conn and on_submit:
            on_submit(api_url, api_key)

    return api_url, api_key


def indicator_overlay_form(
    key: str = "indicators",
    available: list[str] | None = None,
    default_selected: list[str] | None = None,
) -> list[str]:
    """Multi-select for technical indicator overlays."""
    if available is None:
        available = ["SMA_20", "SMA_50", "EMA_20", "RSI_14", "MACD", "BB_20", "ATR_14"]
    if default_selected is None:
        default_selected = ["SMA_20", "SMA_50"]

    selected = st.multiselect(
        "Indicator Overlays",
        available,
        default=default_selected,
        key=f"{key}_selected",
        help="Select indicators to overlay on the chart",
    )

    return selected


def date_range_form(
    key: str = "date_range",
    default_start: str | None = None,
    default_end: str | None = None,
) -> tuple[str | None, str | None]:
    """Date range picker form."""
    col1, col2 = st.columns(2)
    with col1:
        start = st.date_input(
            "Start Date",
            value=default_start,
            key=f"{key}_start",
        )
    with col2:
        end = st.date_input(
            "End Date",
            value=default_end,
            key=f"{key}_end",
        )

    return start.isoformat() if start else None, end.isoformat() if end else None


def export_form(
    key: str = "export",
    filename_prefix: str = "export",
    on_submit: Callable[[str], Any] | None = None,
) -> None:
    """Export/download form."""
    with st.form(key):
        col1, col2 = st.columns([3, 1])
        with col1:
            filename = st.text_input(
                "Filename",
                value=f"{filename_prefix}_{pd.Timestamp.now().strftime('%Y%m%d')}",
                key=f"{key}_filename",
            )
        with col2:
            fmt = st.selectbox(
                "Format",
                ["CSV", "JSON", "Parquet"],
                key=f"{key}_format",
            )

        submitted = st.form_submit_button(
            "📥 Export",
            type="primary",
            use_container_width=True,
        )

        if submitted and on_submit:
            on_submit(f"{filename}.{fmt.lower()}")