"""Prometheus metrics exposure for monitoring."""

from __future__ import annotations

from functools import lru_cache
from typing import Callable

from fastapi import FastAPI, Request, Response
from prometheus_client import Counter, Gauge, Histogram, generate_latest
from prometheus_client.core import CollectorRegistry

from app.middleware.logging import get_correlation_id

# Custom registry to avoid conflicts
REGISTRY = CollectorRegistry()

# HTTP Metrics
HTTP_REQUESTS_TOTAL = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status"],
    registry=REGISTRY,
)

HTTP_REQUEST_DURATION_SECONDS = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency in seconds",
    ["method", "endpoint"],
    registry=REGISTRY,
)

HTTP_REQUESTS_IN_PROGRESS = Gauge(
    "http_requests_in_progress",
    "Number of HTTP requests currently in progress",
    ["method", "endpoint"],
    registry=REGISTRY,
)

# Trading Metrics
ACTIVE_POSITIONS = Gauge(
    "trading_active_positions",
    "Number of open positions",
    registry=REGISTRY,
)

DAILY_REALIZED_PNL = Gauge(
    "trading_daily_realized_pnl",
    "Daily realized P&L in USD",
    registry=REGISTRY,
)

TOTAL_PORTFOLIO_EQUITY = Gauge(
    "trading_total_portfolio_equity",
    "Total portfolio equity in USD",
    registry=REGISTRY,
)

PORTFOLIO_EXPOSURE = Gauge(
    "trading_portfolio_exposure",
    "Current portfolio market exposure in USD",
    registry=REGISTRY,
)

ORDERS_TOTAL = Counter(
    "trading_orders_total",
    "Total orders placed",
    ["side", "status"],
    registry=REGISTRY,
)

POSITION_PNL = Gauge(
    "trading_position_pnl",
    "Position unrealized P&L",
    ["ticker"],
    registry=REGISTRY,
)

# Market Data Metrics
MARKET_DATA_FETCHES_TOTAL = Counter(
    "market_data_fetches_total",
    "Total market data fetch attempts",
    ["provider", "status"],
    registry=REGISTRY,
)

MARKET_DATA_FETCH_DURATION_SECONDS = Histogram(
    "market_data_fetch_duration_seconds",
    "Market data fetch latency in seconds",
    ["provider"],
    registry=REGISTRY,
)

# Research Agent Metrics
RESEARCH_RUNS_TOTAL = Counter(
    "research_runs_total",
    "Total research agent runs",
    ["signal"],
    registry=REGISTRY,
)

STRATEGY_VOTES = Counter(
    "research_strategy_votes_total",
    "Strategy vote counts",
    ["strategy", "vote"],
    registry=REGISTRY,
)


class PrometheusMiddleware:
    """Middleware to collect HTTP metrics."""

    def __init__(self, app: FastAPI):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        method = scope["method"]
        path = scope["path"]

        # Skip metrics endpoint itself
        if path == "/metrics":
            await self.app(scope, receive, send)
            return

        # Increment in-progress
        HTTP_REQUESTS_IN_PROGRESS.labels(method=method, endpoint=path).inc()

        start_time = __import__("time").time()

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                status_code = message["status"]
                duration = __import__("time").time() - start_time

                # Record metrics
                HTTP_REQUESTS_TOTAL.labels(
                    method=method, endpoint=path, status=status_code
                ).inc()
                HTTP_REQUEST_DURATION_SECONDS.labels(
                    method=method, endpoint=path
                ).observe(duration)
                HTTP_REQUESTS_IN_PROGRESS.labels(
                    method=method, endpoint=path
                ).dec()

            await send(message)

        await self.app(scope, receive, send_wrapper)


def setup_metrics(app: FastAPI) -> None:
    """Add Prometheus metrics endpoint and middleware."""

    # Add middleware
    app.add_middleware(PrometheusMiddleware)

    @app.get("/metrics", tags=["Monitoring"])
    async def metrics():
        """Prometheus metrics endpoint."""
        return Response(
            content=generate_latest(REGISTRY),
            media_type="text/plain; version=0.0.4; charset=utf-8",
        )


def update_trading_metrics(
    active_positions: int = 0,
    daily_pnl: float = 0.0,
    equity: float = 0.0,
    exposure: float = 0.0,
    position_pnl: dict[str, float] | None = None,
) -> None:
    """Update trading metrics from portfolio state."""
    ACTIVE_POSITIONS.set(active_positions)
    DAILY_REALIZED_PNL.set(daily_pnl)
    TOTAL_PORTFOLIO_EQUITY.set(equity)
    PORTFOLIO_EXPOSURE.set(exposure)

    if position_pnl:
        for ticker, pnl in position_pnl.items():
            POSITION_PNL.labels(ticker=ticker).set(pnl)


def record_order(side: str, status: str) -> None:
    """Record an order metric."""
    ORDERS_TOTAL.labels(side=side, status=status).inc()


def record_research_run(signal: str) -> None:
    """Record a research agent run."""
    RESEARCH_RUNS_TOTAL.labels(signal=signal).inc()


def record_strategy_vote(strategy: str, vote: str) -> None:
    """Record a strategy vote."""
    STRATEGY_VOTES.labels(strategy=strategy, vote=vote).inc()


def record_market_data_fetch(provider: str, status: str, duration: float) -> None:
    """Record a market data fetch."""
    MARKET_DATA_FETCHES_TOTAL.labels(provider=provider, status=status).inc()
    MARKET_DATA_FETCH_DURATION_SECONDS.labels(provider=provider).observe(duration)