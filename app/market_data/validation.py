"""Validation and UTC normalization for market OHLCV frames."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

import numpy as np
import pandas as pd

OHLCV_COLUMNS = ["open", "high", "low", "close", "volume"]


@dataclass
class DataQualityIssue:
    ticker: str
    timestamp: str | None
    severity: str
    rule: str
    value: dict[str, Any] | None = None
    fix_applied: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ValidationResult:
    def __init__(self) -> None:
        self.issues: list[DataQualityIssue] = []
        self.rows_dropped = 0

    def add(self, issue: DataQualityIssue) -> None:
        self.issues.append(issue)

    @property
    def has_errors(self) -> bool:
        return any(issue.severity == "error" for issue in self.issues)

    @property
    def is_clean(self) -> bool:
        return not self.issues and self.rows_dropped == 0

    def summary(self) -> dict[str, Any]:
        return {"issues": [issue.to_dict() for issue in self.issues], "rows_dropped": self.rows_dropped}


def validate_and_normalize(
    raw: pd.DataFrame, ticker: str
) -> tuple[pd.DataFrame, ValidationResult]:
    """Return valid OHLCV rows in UTC, with every rejected row explained.

    Numeric strings are parsed explicitly. Invalid, missing, non-finite,
    duplicate, or internally inconsistent observations are never repaired.
    """
    result = ValidationResult()
    if not isinstance(raw, pd.DataFrame):
        raise TypeError("Market data must be a pandas DataFrame")
    if raw.empty:
        return pd.DataFrame(columns=OHLCV_COLUMNS), result

    frame = raw.copy()
    frame.columns = [str(column).lower() for column in frame.columns]
    missing = [column for column in OHLCV_COLUMNS if column not in frame.columns]
    if missing:
        result.add(DataQualityIssue(ticker, None, "error", "required_columns", {"missing": missing}))
        result.rows_dropped = len(frame)
        return pd.DataFrame(columns=OHLCV_COLUMNS), result

    if not isinstance(frame.index, pd.DatetimeIndex) and all(
        isinstance(value, (int, float, np.integer, np.floating)) for value in frame.index
    ):
        result.add(DataQualityIssue(ticker, None, "error", "invalid_timestamps", {"reason": "numeric index"}))
        result.rows_dropped = len(frame)
        return pd.DataFrame(columns=OHLCV_COLUMNS), result
    try:
        timestamps = pd.to_datetime(frame.index, utc=True, errors="coerce")
    except (TypeError, ValueError) as exc:
        result.add(DataQualityIssue(ticker, None, "error", "invalid_timestamps", {"error": str(exc)}))
        return pd.DataFrame(columns=OHLCV_COLUMNS), result
    valid_timestamps = ~pd.isna(timestamps)
    if not valid_timestamps.all():
        result.add(DataQualityIssue(ticker, None, "error", "invalid_timestamps", {"count": int((~valid_timestamps).sum())}))
        result.rows_dropped += int((~valid_timestamps).sum())
        frame = frame.loc[valid_timestamps].copy()
        timestamps = timestamps[valid_timestamps]
    frame.index = pd.DatetimeIndex(timestamps, name="timestamp")

    for column in OHLCV_COLUMNS:
        boolean_values = frame[column].map(lambda value: isinstance(value, (bool, np.bool_)))
        if boolean_values.any():
            frame.loc[boolean_values, column] = np.nan
        frame[column] = pd.to_numeric(frame[column], errors="coerce")

    duplicated = frame.index.duplicated(keep="first")
    if duplicated.any():
        count = int(duplicated.sum())
        result.add(DataQualityIssue(ticker, None, "warning", "duplicate_timestamps", {"count": count}, "kept_first"))
        result.rows_dropped += count
        frame = frame.loc[~duplicated].copy()

    numeric = frame.loc[:, OHLCV_COLUMNS].to_numpy(dtype=float)
    finite_rows = np.isfinite(numeric).all(axis=1)
    if (~finite_rows).any():
        result.add(DataQualityIssue(ticker, None, "error", "missing_or_non_numeric_values", {"count": int((~finite_rows).sum())}))
        result.rows_dropped += int((~finite_rows).sum())

    positive_prices = (frame.loc[:, ["open", "high", "low", "close"]] > 0).all(axis=1).to_numpy()
    bad_prices = finite_rows & ~positive_prices
    if bad_prices.any():
        result.add(DataQualityIssue(ticker, None, "error", "non_positive_price", {"count": int(bad_prices.sum())}))

    valid_ohlc = (
        (frame["low"] <= frame["open"])
        & (frame["low"] <= frame["close"])
        & (frame["open"] <= frame["high"])
        & (frame["close"] <= frame["high"])
    ).to_numpy()
    bad_ohlc = finite_rows & ~valid_ohlc
    if bad_ohlc.any():
        result.add(DataQualityIssue(ticker, None, "error", "ohlc_inconsistent", {"count": int(bad_ohlc.sum())}))

    volume = frame["volume"].to_numpy(dtype=float)
    valid_volume = (
        (volume >= 0)
        & (volume == np.floor(volume))
        & (volume <= np.iinfo(np.int64).max)
    )
    bad_volume = finite_rows & ~valid_volume
    if bad_volume.any():
        result.add(DataQualityIssue(ticker, None, "error", "invalid_volume", {"count": int(bad_volume.sum())}))

    keep = finite_rows & positive_prices & valid_ohlc & valid_volume
    dropped_after_duplicate = int((~keep).sum())
    result.rows_dropped += dropped_after_duplicate
    frame = frame.loc[keep, OHLCV_COLUMNS].copy()
    if not frame.empty:
        frame["volume"] = frame["volume"].astype("int64")
        frame["open"] = frame["open"].astype(float)
        frame["high"] = frame["high"].astype(float)
        frame["low"] = frame["low"].astype(float)
        frame["close"] = frame["close"].astype(float)
    return frame, result
