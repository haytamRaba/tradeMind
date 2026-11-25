from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import get_market_data_service
from app.main import app
from app.market_data.providers.interfaces import ProviderInvalidTicker
from app.market_data.service import MarketDataServiceStockNotFound

client = TestClient(app)


@pytest.fixture
def service_override():
    service = Mock()
    app.dependency_overrides[get_market_data_service] = lambda: service
    yield service
    app.dependency_overrides.pop(get_market_data_service, None)


def sample_bar():
    return {
        "timestamp": "2025-01-01T00:00:00+00:00",
        "open": 10,
        "high": 12,
        "low": 9,
        "close": 11,
        "volume": 100,
    }


def test_health_and_swagger_are_available():
    assert client.get("/api/v1/health").json()["status"] == "ok"
    assert client.get("/docs").status_code == 200
    paths = client.get("/openapi.json").json()["paths"]
    assert "/api/v1/health" in paths
    assert "/api/v1/market-data/{ticker}" in paths
    assert "/api/v1/market-data/{ticker}/latest" in paths
    assert "/api/v1/market-data/{ticker}/history" in paths


def test_fetch_endpoint_returns_a_validated_response(service_override):
    service_override.fetch_and_store.return_value = {
        "ticker": "MSFT",
        "period": "3mo",
        "interval": "1d",
        "rows_fetched": 1,
        "rows_persisted": 1,
        "issues": [],
        "data": [sample_bar()],
    }
    response = client.get("/api/v1/market-data/MSFT?period=3mo&interval=1d")
    assert response.status_code == 200
    assert response.json()["data"][0]["close"] == 11
    service_override.fetch_and_store.assert_called_once_with("MSFT", period="3mo", interval="1d")


def test_latest_and_history_endpoints_return_expected_shapes(service_override):
    service_override.fetch_latest_and_store.return_value = {"data": [sample_bar()]}
    latest = client.get("/api/v1/market-data/MSFT/latest")
    assert latest.status_code == 200
    assert latest.json()["close"] == 11
    service_override.get_history.return_value = [{**sample_bar(), "source": "yahoo_finance"}]
    history = client.get(
        "/api/v1/market-data/MSFT/history"
        "?start=2025-01-01T00:00:00Z&end=2025-01-31T23:59:59Z"
    )
    assert history.status_code == 200
    assert history.json()["count"] == 1
    service_override.fetch_and_store.assert_called_once()


@pytest.mark.parametrize(
    ("error", "path", "status"),
    [
        (ProviderInvalidTicker("bad ticker"), "/api/v1/market-data/NOPE", 404),
        (ValueError("bad interval"), "/api/v1/market-data/MSFT", 422),
        (MarketDataServiceStockNotFound("no stored bars"), "/api/v1/market-data/MSFT/history", 404),
    ],
)
def test_api_maps_errors_to_meaningful_status_codes(service_override, error, path, status):
    service_override.fetch_and_store.side_effect = error
    service_override.get_history.side_effect = error
    response = client.get(path)
    assert response.status_code == status
    assert "detail" in response.json()
