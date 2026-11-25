"""KPI cards, progress bars, and metric display components for Streamlit frontend."""

from __future__ import annotations

import streamlit as st
from typing import Any
from decimal import Decimal


def metric_card(
    label: str,
    value: str | int | float,
    delta: str | int | float | None = None,
    delta_color: str = "normal",
    help_text: str | None = None,
) -> None:
    """Display a single metric card with optional delta."""
    st.metric(
        label=label,
        value=value,
        delta=delta,
        delta_color=delta_color,
        help=help_text,
    )


def metric_row(
    metrics: list[dict[str, Any]],
    columns: int = 4,
) -> None:
    """Display a row of metric cards."""
    cols = st.columns(columns)
    for i, m in enumerate(metrics):
        with cols[i % columns]:
            metric_card(
                label=m.get("label", ""),
                value=m.get("value", ""),
                delta=m.get("delta"),
                delta_color=m.get("delta_color", "normal"),
                help_text=m.get("help"),
            )


def kpi_card(
    title: str,
    value: str | int | float,
    subtitle: str | None = None,
    icon: str | None = None,
    color: str = "default",
) -> None:
    """Display a styled KPI card with icon and color."""
    colors = {
        "default": "#1f77b4",
        "green": "#2ca02c",
        "red": "#d62728",
        "orange": "#ff7f0e",
        "purple": "#9467bd",
    }
    border_color = colors.get(color, colors["default"])

    icon_html = f"<span style='font-size: 1.5rem;'>{icon}</span> " if icon else ""

    st.markdown(
        f"""
        <div style="
            border-left: 4px solid {border_color};
            padding: 1rem;
            border-radius: 0.5rem;
            background-color: {'rgba(46, 160, 44, 0.1)' if color == 'green' else 'rgba(214, 39, 40, 0.1)' if color == 'red' else 'rgba(255, 127, 14, 0.1)' if color == 'orange' else 'rgba(31, 119, 180, 0.1)'};
            margin-bottom: 0.5rem;
        ">
            <div style="font-size: 0.875rem; color: #666; font-weight: 500;">
                {icon_html}{title}
            </div>
            <div style="font-size: 1.5rem; font-weight: 600; margin-top: 0.25rem;">
                {value}
            </div>
            {f'<div style="font-size: 0.75rem; color: #888; margin-top: 0.25rem;">{subtitle}</div>' if subtitle else ''}
        </div>
        """,
        unsafe_allow_html=True,
    )


def progress_bar_card(
    label: str,
    value: float,
    maximum: float,
    unit: str = "%",
    color: str = "blue",
    show_percentage: bool = True,
) -> None:
    """Display a progress bar with label and value."""
    percentage = min(max(value / maximum * 100, 0), 100) if maximum > 0 else 0

    colors = {
        "blue": "#1f77b4",
        "green": "#2ca02c",
        "red": "#d62728",
        "orange": "#ff7f0e",
        "purple": "#9467bd",
    }
    bar_color = colors.get(color, colors["blue"])

    st.markdown(
        f"""
        <div style="margin-bottom: 0.75rem;">
            <div style="display: flex; justify-content: space-between; margin-bottom: 0.25rem;">
                <span style="font-weight: 500;">{label}</span>
                <span style="font-family: monospace;">{value:,.2f} / {maximum:,.2f} {unit}</span>
            </div>
            <div style="
                height: 8px;
                background-color: #e0e0e0;
                border-radius: 4px;
                overflow: hidden;
            ">
                <div style="
                    width: {percentage}%;
                    height: 100%;
                    background-color: {bar_color};
                    border-radius: 4px;
                    transition: width 0.3s ease;
                "></div>
            </div>
            {f'<div style="text-align: right; font-size: 0.75rem; color: #888; margin-top: 0.25rem;">{percentage:.1f}%</div>' if show_percentage else ''}
        </div>
        """,
        unsafe_allow_html=True,
    )


def exposure_progress_bar(
    current_exposure: float,
    max_exposure: float,
    equity: float,
) -> None:
    """Display portfolio exposure progress bar with risk thresholds."""
    pct = (current_exposure / equity * 100) if equity > 0 else 0
    max_pct = (max_exposure / equity * 100) if equity > 0 else 0

    # Determine color based on risk level
    if pct >= max_pct * 0.9:
        color = "red"
    elif pct >= max_pct * 0.7:
        color = "orange"
    else:
        color = "green"

    progress_bar_card(
        label="Portfolio Exposure",
        value=current_exposure,
        maximum=max_exposure,
        unit="$",
        color=color,
        show_percentage=True,
    )

    # Show percentage of equity
    st.caption(f"{pct:.1f}% of equity (limit: {max_pct:.1f}%)")


def position_risk_card(
    ticker: str,
    entry_price: float,
    current_price: float,
    stop_loss: float,
    take_profit: float | None,
    quantity: float,
    equity: float,
) -> None:
    """Display a position risk breakdown card."""
    unrealized_pnl = (current_price - entry_price) * quantity
    unrealized_pct = (current_price - entry_price) / entry_price * 100
    risk_per_share = entry_price - stop_loss
    total_risk = risk_per_share * quantity
    risk_pct_equity = total_risk / equity * 100 if equity > 0 else 0
    position_value = current_price * quantity

    with st.expander(f"{ticker} - {quantity:,.0f} shares", expanded=False):
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Entry", f"${entry_price:,.2f}")
        c2.metric("Current", f"${current_price:,.2f}", f"{unrealized_pct:+.2f}%")
        c3.metric("Stop Loss", f"${stop_loss:,.2f}", f"Risk/share: ${risk_per_share:,.2f}")
        c4.metric("Take Profit", f"${take_profit:,.2f}" if take_profit else "N/A")

        c5, c6, c7 = st.columns(3)
        c5.metric("Position Value", f"${position_value:,.2f}")
        c6.metric("Total Risk", f"${total_risk:,.2f}", f"{risk_pct_equity:.2f}% of equity")
        c7.metric("Unrealized P&L", f"${unrealized_pnl:,.2f}")


def portfolio_summary_cards(
    equity: float,
    cash: float,
    exposure: float,
    positions_count: int,
    unrealized_pnl: float,
    realized_today: float,
    starting_cash: float,
) -> None:
    """Display portfolio summary KPI cards."""
    total_return = ((equity - starting_cash) / starting_cash * 100) if starting_cash > 0 else 0
    cash_pct = (cash / equity * 100) if equity > 0 else 0
    exposure_pct = (exposure / equity * 100) if equity > 0 else 0

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Equity", f"${equity:,.2f}", f"{total_return:+.2f}%")
    m2.metric("Cash", f"${cash:,.2f}", f"{cash_pct:.1f}% of equity")
    m3.metric("Exposure", f"${exposure:,.2f}", f"{exposure_pct:.1f}%")
    m4.metric("Unrealized P&L", f"${unrealized_pnl:,.2f}")

    m5, m6, m7 = st.columns(3)
    m5.metric("Realized Today", f"${realized_today:,.2f}")
    m6.metric("Starting Cash", f"${starting_cash:,.2f}")
    m7.metric("Positions", positions_count)


def performance_summary_cards(
    total_trades: int,
    win_rate: float,
    total_pnl: float,
    avg_win: float,
    avg_loss: float,
    profit_factor: float,
    gross_profit: float,
    gross_loss: float,
) -> None:
    """Display performance summary KPI cards."""
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total Trades", total_trades)
    m2.metric("Win Rate", f"{win_rate:.1f}%")
    m3.metric("Total P&L", f"${total_pnl:,.2f}")
    m4.metric("Profit Factor", f"{profit_factor:.2f}")

    m5, m6, m7 = st.columns(3)
    m5.metric("Gross Profit", f"${gross_profit:,.2f}")
    m6.metric("Gross Loss", f"${gross_loss:,.2f}")
    m7.metric("Avg Win / Loss", f"${avg_win:,.2f} / ${avg_loss:,.2f}")


def risk_limit_card(
    name: str,
    current: float,
    limit: float,
    unit: str = "%",
    invert: bool = False,
) -> None:
    """Display a risk limit card with progress bar."""
    pct = (current / limit * 100) if limit > 0 else 0

    if invert:
        # For limits where lower is worse (e.g., cash reserve)
        status = "🔴" if pct > 100 else "🟢"
        color = "red" if pct > 100 else "green"
    else:
        # For limits where higher is worse (e.g., exposure)
        status = "🔴" if pct > 100 else ("🟡" if pct > 80 else "🟢")
        if pct > 100:
            color = "red"
        elif pct > 80:
            color = "orange"
        else:
            color = "green"

    st.markdown(
        f"""
        <div style="
            border-left: 4px solid {color};
            padding: 0.75rem;
            border-radius: 0.5rem;
            background-color: {'rgba(214, 39, 40, 0.1)' if color == 'red' else 'rgba(255, 127, 14, 0.1)' if color == 'orange' else 'rgba(46, 160, 44, 0.1)'};
            margin-bottom: 0.5rem;
        ">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <span style="font-weight: 500;">{name}</span>
                <span>{status}</span>
            </div>
            <div style="font-size: 1.25rem; font-weight: 600; margin: 0.25rem 0;">
                {current:,.2f} {unit} / {limit:,.2f} {unit}
            </div>
            <div style="
                height: 6px;
                background-color: #e0e0e0;
                border-radius: 3px;
                overflow: hidden;
            ">
                <div style="
                    width: {min(pct, 100)}%;
                    height: 100%;
                    background-color: {color};
                    border-radius: 3px;
                "></div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def format_currency(value: Decimal | float | int) -> str:
    """Format a number as currency string."""
    return f"${float(value):,.2f}"


def format_percentage(value: Decimal | float | int) -> str:
    """Format a number as percentage string."""
    return f"{float(value):.2f}%"


def format_number(value: Decimal | float | int, decimals: int = 2) -> str:
    """Format a number with specified decimals."""
    return f"{float(value):,.{decimals}f}"