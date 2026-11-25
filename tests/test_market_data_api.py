from datetime import datetime, timezone
from unittest.mock import Mock

import pytest
from fastapi import HTTPException

from app.api.routes.market_data import (
    _raise_market_data_error,
    get_latest_market_data,
    get_market_data,
    get_market_history,
    health,
)
from app.api.schemas.market_data import MarketDataResponse, MarketHistoryResponse
from app.main import app
from app.market_data.providers.interfaces import ProviderInvalidTicker
from app.market_data.service import MarketDataServiceStockNotFound


def test_health_and_openapi_paths_are_available():
    assert health().status == "ok"
    paths = app.openapi()["paths"]
    assert "/api/v1/health" in paths
    assert "/api/v1/market-data/{ticker}" in paths
    assert "/api/v1/market-data/{ticker}/latest" in paths
    assert "/api/v1/market-data/{ticker}/history" in paths


def test_fetch_endpoint_returns_schema_validated_data():
    service = Mock()
    service.fetch_and_store.return_value = {
        "ticker": "MSFT",
        "period": "1mo",
        "interval": "1d",
        "rows_fetched": 1,
        "rows_persisted": 1,
        "issues": [],
        "data": [{
            "timestamp": "2025-01-01T00:00:00+00:00",
            "open": 10,
            "high": 12,
            "low": 9,
            "close": 11,
            "volume": 100,
        }],
    }
    response = MarketDataResponse.model_validate(get_market_data("MSFT", service=service))
    assert response.data[0].close == 11
    service.fetch_and_store.assert_called_once_with("MSFT", period="1mo", interval="1d")


def test_latest_and_history_endpoints_return_api_shapes():
    service = Mock()
    service.fetch_latest_and_store.return_value = {
        "data": [{
            "timestamp": "2025-01-01T00:00:00+00:00",
            "open": 10,
            "high": 12,
            "low": 9,
            "close": 11,
            "volume": 100,
        }]
    }
    latest = get_latest_market_data("MSFT", service=service)
    assert latest["close"] == 11
    service.get_history.return_value = [
        {
            "timestamp": datetime(2025, 1, 1, tzinfo=timezone.utc).isoformat(),
            "open": 10,
            "high": 12,
            "low": 9,
            "close": 11,
            "volume": 100,
            "source": "yahoo_finance",
        }
    ]
    history = MarketHistoryResponse.model_validate(get_market_history("MSFT", service=service))
    assert history.count == 1


@pytest.mark.parametrize(
    ("error", "status"),
    [
        (ProviderInvalidTicker("bad ticker"), 404),
        (MarketDataServiceStockNotFound("no stored bars"), 404),
        (ValueError("bad interval"), 422),
    ],
)
def test_api_maps_errors_to_meaningful_status_codes(error, status):
    with pytest.raises(HTTPException) as raised:
        _raise_market_data_error(error)
    assert raised.value.status_code == status
