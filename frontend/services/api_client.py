"""HTTP client for calling FastAPI backend."""

from __future__ import annotations

from typing import Any

import httpx
import streamlit as st

from frontend.config import get_frontend_settings


class APIClient:
    """Thin wrapper around httpx for backend communication."""

    def __init__(self, api_key: str | None = None):
        self.settings = get_frontend_settings()
        self.api_key = api_key or st.session_state.get("api_key")
        self._client: httpx.AsyncClient | None = None

    @property
    def client(self) -> httpx.AsyncClient:
        """Lazily create async client."""
        if self._client is None:
            headers = {}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"
            self._client = httpx.AsyncClient(
                base_url=self.settings.api_base_url,
                timeout=self.settings.api_timeout,
                headers=headers,
            )
        return self._client

    async def close(self):
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit - close client."""
        await self.close()

    # Market Data endpoints
    async def get_market_data(self, ticker: str, period: str = "1mo", interval: str = "1d") -> dict[str, Any]:
        """Fetch market data for a ticker."""
        resp = await self.client.get(
            f"/api/v1/market-data/{ticker}",
            params={"period": period, "interval": interval},
        )
        resp.raise_for_status()
        return resp.json()

    async def get_latest_price(self, ticker: str) -> dict[str, Any]:
        """Get latest price for a ticker."""
        resp = await self.client.get(f"/api/v1/market-data/{ticker}/latest")
        resp.raise_for_status()
        return resp.json()

    async def get_history(self, ticker: str, start: str | None = None, end: str | None = None) -> dict[str, Any]:
        """Get historical data for a ticker."""
        params = {}
        if start:
            params["start"] = start
        if end:
            params["end"] = end
        resp = await self.client.get(f"/api/v1/market-data/{ticker}/history", params=params)
        resp.raise_for_status()
        return resp.json()

    # Research Agent endpoints
    async def run_research(self, ticker: str, period: str = "6mo", interval: str = "1d") -> dict[str, Any]:
        """Run research agent analysis."""
        resp = await self.client.post(
            "/api/v1/agents/research/{ticker}".format(ticker=ticker),
            params={"period": period, "interval": interval},
        )
        resp.raise_for_status()
        return resp.json()

    # Trading Agent endpoints
    async def execute_trade(self, ticker: str, idempotency_key: str) -> dict[str, Any]:
        """Execute paper trade based on research."""
        resp = await self.client.post(
            f"/api/v1/agents/trading/{ticker}/execute",
            json={"idempotency_key": idempotency_key},
        )
        resp.raise_for_status()
        return resp.json()

    # Paper Trading endpoints
    async def get_portfolio(self) -> dict[str, Any]:
        """Get paper trading portfolio."""
        resp = await self.client.get("/api/v1/paper-trading/portfolio")
        resp.raise_for_status()
        return resp.json()

    async def get_orders(self, limit: int = 100) -> list[dict[str, Any]]:
        """Get paper trading order history."""
        resp = await self.client.get("/api/v1/paper-trading/orders", params={"limit": limit})
        resp.raise_for_status()
        return resp.json()

    async def monitor_positions(self) -> dict[str, Any]:
        """Monitor and trigger protective stops."""
        resp = await self.client.post("/api/v1/paper-trading/monitor")
        resp.raise_for_status()
        return resp.json()

    # Health check
    async def health_check(self) -> dict[str, Any]:
        """Check API health."""
        resp = await self.client.get("/health")
        return resp.json()


# Singleton instance for session
@st.cache_resource
def get_api_client(api_key: str | None = None) -> APIClient:
    """Get cached API client instance."""
    return APIClient(api_key)


# Helper function for easy one-shot calls
async def _run_with_client(api_key: str | None, coro_factory):
    """Run a coroutine with a fresh client and close it."""
    client = APIClient(api_key)
    try:
        return await coro_factory(client)
    finally:
        await client.close()