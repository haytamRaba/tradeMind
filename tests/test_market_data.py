from unittest.mock import Mock

import pandas as pd
import pytest

from app.database.repositories import HistoricalPriceRepository, StockRepository
from app.market_data.providers.interfaces import (
    ProviderEmptyResponse,
    ProviderInvalidTicker,
    ProviderNetworkError,
)
from app.market_data.providers.yahoo import YahooFinanceProvider
from app.market_data.service import MarketDataService
from app.market_data.validation import validate_and_normalize


def test_yahoo_provider_passes_ticker_period_interval_and_normalizes(monkeypatch, ohlcv_frame):
    instrument = Mock()
    instrument.history.return_value = ohlcv_frame
    monkeypatch.setattr("app.market_data.providers.yahoo.yf.Ticker", lambda ticker: instrument)

    result = YahooFinanceProvider().fetch_history("msft", period="3mo", interval="1d")

    assert list(result) == ["MSFT"]
    assert result["MSFT"].columns.tolist() == ["open", "high", "low", "close", "volume"]
    instrument.history.assert_called_once_with(period="3mo", interval="1d", auto_adjust=False, actions=False)


def test_yahoo_provider_rejects_unsupported_interval():
    with pytest.raises(ValueError, match="Unsupported data interval"):
        YahooFinanceProvider().fetch_history("MSFT", interval="10m")


def test_yahoo_provider_maps_empty_and_network_errors(monkeypatch):
    instrument = Mock()
    instrument.history.return_value = pd.DataFrame()
    instrument.get_info.return_value = {}
    monkeypatch.setattr("app.market_data.providers.yahoo.yf.Ticker", lambda ticker: instrument)
    with pytest.raises(ProviderInvalidTicker):
        YahooFinanceProvider().fetch_history("NOPE")

    instrument.get_info.return_value = {"symbol": "MSFT", "shortName": "Microsoft"}
    with pytest.raises(ProviderEmptyResponse):
        YahooFinanceProvider().fetch_history("MSFT")

    instrument.history.side_effect = RuntimeError("temporarily unavailable")
    with pytest.raises(ProviderNetworkError):
        YahooFinanceProvider().fetch_history("MSFT")


def test_yahoo_provider_returns_available_company_information(monkeypatch):
    instrument = Mock()
    instrument.get_info.return_value = {
        "shortName": "Example Inc.",
        "exchange": "NMS",
        "currency": "USD",
        "country": "United States",
    }
    monkeypatch.setattr("app.market_data.providers.yahoo.yf.Ticker", lambda ticker: instrument)
    details = YahooFinanceProvider().fetch_company_info("EXAMPLE")
    assert details["name"] == "Example Inc."
    assert details["exchange"] == "NMS"


def test_validation_normalizes_names_and_timezone_without_changing_prices(ohlcv_frame):
    normalized, result = validate_and_normalize(ohlcv_frame, "MSFT")
    assert normalized.columns.tolist() == ["open", "high", "low", "close", "volume"]
    assert str(normalized.index.tz) == "UTC"
    assert normalized.iloc[0]["close"] == 11.0
    assert result.is_clean


def test_validation_rejects_invalid_rows_and_reports_duplicate_timestamps(ohlcv_frame):
    frame = pd.concat([ohlcv_frame, ohlcv_frame.iloc[[0]]])
    frame["Volume"] = frame["Volume"].astype(float)
    frame.iloc[1, frame.columns.get_loc("Close")] = -2
    frame.iloc[2, frame.columns.get_loc("Volume")] = 3.5
    normalized, result = validate_and_normalize(frame, "MSFT")
    assert len(normalized) == 1
    rules = {issue.rule for issue in result.issues}
    assert {"duplicate_timestamps", "non_positive_price", "invalid_volume"} <= rules
    assert result.rows_dropped == 3


def test_validation_reports_missing_columns(ohlcv_frame):
    normalized, result = validate_and_normalize(ohlcv_frame.drop(columns="Volume"), "MSFT")
    assert normalized.empty
    assert result.has_errors
    assert result.issues[0].rule == "required_columns"


def test_service_persists_and_updates_duplicate_bars(db_session, ohlcv_frame):
    provider = Mock()
    provider.fetch_history.return_value = {"MSFT": ohlcv_frame}
    provider.fetch_company_info.return_value = {"name": "Microsoft", "currency": "USD"}
    service = MarketDataService(provider=provider, session=db_session)

    first = service.fetch_and_store("msft", period="3mo", interval="1d")
    ohlcv_frame.loc[ohlcv_frame.index[-1], "Close"] = 13.5
    provider.fetch_history.return_value = {"MSFT": ohlcv_frame}
    second = service.fetch_and_store("MSFT", period="3mo", interval="1d")

    assert first["rows_persisted"] == 3
    assert second["rows_persisted"] == 3
    assert StockRepository(db_session).get_by_symbol("MSFT").name == "Microsoft"
    assert HistoricalPriceRepository(db_session).count_for_symbol("MSFT") == 3
    assert service.get_latest("MSFT")[0]["close"] == 13.5


def test_service_uses_provider_latest_and_persists_it(db_session):
    provider = Mock()
    provider.fetch_latest.return_value = {
        "ticker": "MSFT",
        "timestamp": "2025-01-01T16:00:00+00:00",
        "open": 10,
        "high": 12,
        "low": 9,
        "close": 11,
        "volume": 100,
    }
    provider.fetch_company_info.return_value = {}
    result = MarketDataService(provider=provider, session=db_session).fetch_latest_and_store("MSFT")
    assert result["rows_persisted"] == 1
    assert HistoricalPriceRepository(db_session).count_for_symbol("MSFT") == 1
