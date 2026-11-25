"""Plotly chart components for Streamlit."""

from __future__ import annotations

from typing import Any

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots


def create_candlestick_chart(
    data: list[dict[str, Any]],
    indicators: dict[str, float | None] | None = None,
    title: str = "Price Chart",
) -> go.Figure:
    """Create candlestick chart with optional indicator overlays."""
    if not data:
        fig = go.Figure()
        fig.add_annotation(text="No data available", xref="paper", yref="paper", x=0.5, y=0.5, showarrow=False)
        return fig

    df = pd.DataFrame(data)
    df["timestamp"] = pd.to_datetime(df["timestamp"])

    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.05,
        row_heights=[0.7, 0.3],
        subplot_titles=(title, "Volume"),
    )

    # Candlestick
    fig.add_trace(
        go.Candlestick(
            x=df["timestamp"],
            open=df["open"],
            high=df["high"],
            low=df["low"],
            close=df["close"],
            name="OHLC",
        ),
        row=1, col=1,
    )

    # Add SMA overlays if indicators provided
    if indicators:
        sma_20 = indicators.get("sma_20")
        sma_50 = indicators.get("sma_50")
        if sma_20:
            fig.add_trace(
                go.Scatter(x=df["timestamp"], y=[sma_20] * len(df), name="SMA 20", line=dict(color="orange", width=1)),
                row=1, col=1,
            )
        if sma_50:
            fig.add_trace(
                go.Scatter(x=df["timestamp"], y=[sma_50] * len(df), name="SMA 50", line=dict(color="blue", width=1)),
                row=1, col=1,
            )

    # Volume bars
    colors = ["green" if c >= o else "red" for c, o in zip(df["close"], df["open"])]
    fig.add_trace(
        go.Bar(x=df["timestamp"], y=df["volume"], name="Volume", marker_color=colors, opacity=0.5),
        row=2, col=1,
    )

    fig.update_layout(
        xaxis_rangeslider_visible=False,
        height=600,
        template="plotly_white",
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    fig.update_yaxes(title_text="Price ($)", row=1, col=1)
    fig.update_yaxes(title_text="Volume", row=2, col=1)

    return fig


def create_indicator_chart(
    data: list[dict[str, Any]],
    indicator_name: str,
    indicator_values: list[float] | None = None,
    title: str = "",
) -> go.Figure:
    """Create a chart for a single indicator (RSI, MACD, etc.)."""
    if not data:
        fig = go.Figure()
        fig.add_annotation(text="No data available", xref="paper", yref="paper", x=0.5, y=0.5, showarrow=False)
        return fig

    df = pd.DataFrame(data)
    df["timestamp"] = pd.to_datetime(df["timestamp"])

    fig = go.Figure()

    if indicator_name.upper() == "RSI":
        if indicator_values:
            fig.add_trace(go.Scatter(x=df["timestamp"], y=indicator_values, name="RSI", line=dict(color="purple")))
        fig.add_hline(y=70, line_dash="dash", line_color="red", annotation_text="Overbought (70)")
        fig.add_hline(y=30, line_dash="dash", line_color="green", annotation_text="Oversold (30)")
        fig.add_hline(y=50, line_dash="dot", line_color="gray")
        fig.update_yaxes(range=[0, 100], title_text="RSI")

    elif indicator_name.upper() == "MACD":
        pass  # Would need MACD line, signal line, histogram from indicators

    elif indicator_name.upper() == "ATR":
        if indicator_values:
            fig.add_trace(go.Scatter(x=df["timestamp"], y=indicator_values, name="ATR", line=dict(color="orange")))
        fig.update_yaxes(title_text="ATR")

    fig.update_layout(
        height=300,
        template="plotly_white",
        title=title or indicator_name,
        showlegend=True,
    )

    return fig


def create_equity_curve(equity_history: list[dict[str, Any]]) -> go.Figure:
    """Create equity curve chart from portfolio history."""
    if not equity_history:
        fig = go.Figure()
        fig.add_annotation(text="No equity data", xref="paper", yref="paper", x=0.5, y=0.5, showarrow=False)
        return fig

    df = pd.DataFrame(equity_history)
    df["timestamp"] = pd.to_datetime(df["timestamp"])

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df["timestamp"], y=df["equity"], name="Equity", fill="tozeroy", line=dict(color="green")))
    fig.add_trace(go.Scatter(x=df["timestamp"], y=df["cash"], name="Cash", line=dict(color="blue", dash="dash")))

    fig.update_layout(
        height=400,
        template="plotly_white",
        title="Portfolio Equity Curve",
        xaxis_title="Date",
        yaxis_title="Value ($)",
        showlegend=True,
    )

    return fig


def create_pnl_chart(pnl_data: list[dict[str, Any]]) -> go.Figure:
    """Create P&L bar chart."""
    if not pnl_data:
        fig = go.Figure()
        fig.add_annotation(text="No P&L data", xref="paper", yref="paper", x=0.5, y=0.5, showarrow=False)
        return fig

    df = pd.DataFrame(pnl_data)
    colors = ["green" if p >= 0 else "red" for p in df["pnl"]]

    fig = go.Figure()
    fig.add_trace(go.Bar(x=df["ticker"], y=df["pnl"], name="Realized P&L", marker_color=colors))

    fig.update_layout(
        height=300,
        template="plotly_white",
        title="Realized P&L by Trade",
        yaxis_title="P&L ($)",
        showlegend=False,
    )

    return fig