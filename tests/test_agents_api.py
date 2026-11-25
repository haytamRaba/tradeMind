from decimal import Decimal
from unittest.mock import Mock

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app.agents.research_agent.nodes import build_research_report
from app.api.dependencies import get_research_agent, get_trading_agent
from app.main import app
from app.market_data.providers.interfaces import ProviderInvalidTicker

client = TestClient(app)


@pytest.fixture
def agent_overrides():
    research = Mock()
    trading = Mock()
    index = pd.date_range("2025-01-01", periods=60, freq="D", tz="UTC")
    bars = [
        {
            "timestamp": timestamp.isoformat(),
            "open": 100 + offset,
            "high": 101 + offset,
            "low": 99 + offset,
            "close": 100 + offset,
            "volume": 100_000,
        }
        for offset, timestamp in enumerate(index)
    ]
    report = build_research_report("MSFT", bars, [])
    research.run.return_value = report
    trading.execute.return_value = {
        "order_id": 1,
        "ticker": "MSFT",
        "side": report.signal.value,
        "status": "FILLED",
        "quantity": Decimal("5"),
        "execution_price": Decimal("159"),
        "stop_loss": Decimal("157"),
        "take_profit": Decimal("162"),
        "realized_pnl": Decimal("0"),
        "cash_after": Decimal("9205"),
        "idempotency_key": "api-test-key",
        "message": "Paper order filled.",
        "replayed": False,
    }
    trading.get_portfolio.return_value = {
        "name": "default",
        "starting_cash": Decimal("10000"),
        "cash": Decimal("9205"),
        "equity": Decimal("10000"),
        "market_exposure": Decimal("795"),
        "unrealized_pnl": Decimal("0"),
        "realized_pnl_today": Decimal("0"),
        "positions": [],
    }
    trading.get_orders.return_value = []
    trading.monitor_positions.return_value = {"refreshed": [], "errors": [], "exits": []}
    app.dependency_overrides[get_research_agent] = lambda: research
    app.dependency_overrides[get_trading_agent] = lambda: trading
    yield research, trading
    app.dependency_overrides.pop(get_research_agent, None)
    app.dependency_overrides.pop(get_trading_agent, None)


def test_research_agent_endpoint_returns_structured_analysis(agent_overrides):
    research, _ = agent_overrides
    response = client.post("/api/v1/agents/research/MSFT?period=6mo&interval=1d")
    assert response.status_code == 200
    assert response.json()["ticker"] == "MSFT"
    assert "strategies" in response.json()["decision"]
    research.run.assert_called_once_with("MSFT", period="6mo", interval="1d")


def test_trading_endpoint_executes_only_the_agent_report(agent_overrides):
    research, trading = agent_overrides
    response = client.post(
        "/api/v1/agents/trading/MSFT/execute",
        json={"idempotency_key": "api-test-key"},
    )
    assert response.status_code == 200
    assert response.json()["execution"]["status"] == "FILLED"
    assert response.json()["research"]["ticker"] == "MSFT"
    trading.execute.assert_called_once()
    assert trading.execute.call_args.args[0] == research.run.return_value


def test_paper_portfolio_order_and_monitor_endpoints(agent_overrides):
    _, trading = agent_overrides
    assert client.get("/api/v1/paper-trading/portfolio").status_code == 200
    assert client.get("/api/v1/paper-trading/orders").json() == []
    assert client.post("/api/v1/paper-trading/monitor").json()["exits"] == []
    trading.get_orders.assert_called_once_with(100)


def test_research_agent_errors_use_market_data_status_codes(agent_overrides):
    research, _ = agent_overrides
    research.run.side_effect = ProviderInvalidTicker("Unknown ticker")
    response = client.post("/api/v1/agents/research/NOPE")
    assert response.status_code == 404
    assert "Unknown ticker" in response.json()["detail"]


def test_trading_request_requires_idempotency_key():
    response = client.post("/api/v1/agents/trading/MSFT/execute", json={})
    assert response.status_code == 422
