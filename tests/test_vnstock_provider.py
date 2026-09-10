"""Offline tests: no internet, credentials or LLM required."""

from datetime import datetime, timedelta, timezone
from unittest.mock import Mock

import pandas as pd
import pytest

from pit_haf.data.vnstock_provider import (
    MarketDataError,
    VietnamMarketDataProvider,
    normalize_ohlcv,
)


@pytest.fixture
def raw():
    frame = pd.DataFrame({
        "time": ["2024-01-03 07:00:00", "2024-01-02 07:00:00"],
        "open": [100.0, 98.0],
        "high": [104.0, 102.0],
        "low": [99.0, 97.0],
        "close": [103.0, 100.0],
        "volume": [1200, 1000],
    })
    frame.attrs = {"source": "KBS", "symbol": "FPT", "interval": "1D"}
    return frame


def normalize(raw, **overrides):
    options = {"start": "2024-01-01", "end": "2024-01-03", "asset_type": "equity"}
    return normalize_ohlcv(raw, **(options | overrides))


def test_equity_units_sorting_and_source_not_mutated(raw):
    original = raw.copy(deep=True)
    result = normalize(raw)
    assert result["close"].tolist() == [100_000, 103_000]
    assert result["volume"].tolist() == [1000, 1200]
    assert result["session_date"].dt.hour.tolist() == [0, 0]
    assert result.attrs["price_unit"] == "VND"
    pd.testing.assert_frame_equal(raw, original)


def test_index_stays_in_points(raw):
    result = normalize(raw, asset_type="index")
    assert result["close"].tolist() == [100, 103]
    assert result.attrs["price_unit"] == "points"


def test_inclusive_range_excludes_later_data(raw):
    result = normalize(raw, start="2024-01-02", end="2024-01-02")
    assert result["close"].tolist() == [100_000]
    assert result["session_date"].tolist() == [pd.Timestamp("2024-01-02")]


def test_timezones_use_vietnam_session_date(raw):
    raw["time"] = pd.to_datetime(["2024-01-02T18:00:00Z", "2024-01-01T18:00:00Z"])
    result = normalize(raw, start="2024-01-02", end="2024-01-02")
    assert result["close"].tolist() == [100_000]


@pytest.mark.parametrize("column,value", [
    ("close", None), ("open", float("inf")), ("close", "bad"),
    ("open", 0), ("volume", -1), ("volume", 1.5),
    ("low", 105), ("high", 90), ("time", None), ("time", "bad"),
])
def test_invalid_bars_raise_instead_of_silently_disappearing(raw, column, value):
    raw[column] = raw[column].astype(object)
    raw.loc[0, column] = value
    with pytest.raises(MarketDataError):
        normalize(raw)


def test_duplicate_sessions_are_not_arbitrarily_dropped(raw):
    raw.loc[0, "time"] = "2024-01-02 18:00:00"
    with pytest.raises(MarketDataError, match="same session"):
        normalize(raw)


def test_empty_range_is_an_error(raw):
    with pytest.raises(MarketDataError, match="No rows"):
        normalize(raw, start="2024-01-06", end="2024-01-07")


def test_missing_column_is_an_error(raw):
    with pytest.raises(MarketDataError, match="Missing columns"):
        normalize(raw.drop(columns="close"))


def test_unknown_source_must_not_get_kbs_price_multiplier(raw):
    raw.attrs["source"] = "unverified-source"
    with pytest.raises(MarketDataError, match="unknown price unit"):
        normalize(raw)


def test_reversed_date_range(raw):
    with pytest.raises(ValueError, match="on or before"):
        normalize(raw, start="2024-01-04")


def test_future_end_date_is_not_a_completed_bar(raw):
    with pytest.raises(ValueError, match="past end date"):
        future = datetime.now(timezone.utc).date() + timedelta(days=2)
        normalize(raw, end=future.isoformat())


def test_provider_provenance_and_more_than_100_rows(monkeypatch):
    raw = pd.DataFrame({
        "time": pd.bdate_range("2024-01-01", periods=120),
        "open": 100, "high": 101, "low": 99, "close": 100, "volume": 1000,
    })
    raw.attrs = {"source": "KBS", "symbol": "FPT"}
    fake_asset = Mock()
    fake_asset.ohlcv.return_value = raw
    fake_market = Mock()
    fake_market.equity.return_value = fake_asset
    # Replace only the network-facing import; normalization still runs for real.
    import sys
    from types import ModuleType

    fake_vnstock = ModuleType("vnstock.ui")
    fake_vnstock.Market = lambda: fake_market
    monkeypatch.setitem(sys.modules, "vnstock.ui", fake_vnstock)
    result = VietnamMarketDataProvider().get_prices(" fpt ", "2024-01-01", "2024-06-30")
    assert len(result) == 120
    assert result.attrs["symbol"] == "FPT"
    assert result.attrs["retrieved_at"].endswith("+00:00")
    fake_asset.ohlcv.assert_called_once_with(
        start="2024-01-01", end="2024-06-30", interval="1D", count=None, source="kbs"
    )


def test_provider_rejects_wrong_symbol(raw, monkeypatch):
    monkeypatch.setattr(VietnamMarketDataProvider, "_download", staticmethod(lambda *args: raw))
    with pytest.raises(MarketDataError, match="symbol mismatch"):
        VietnamMarketDataProvider().get_prices("HPG", "2024-01-01", "2024-01-03")


def test_index_cannot_be_misclassified_as_equity():
    with pytest.raises(ValueError, match="equity ticker"):
        VietnamMarketDataProvider().get_prices("VNINDEX", "2024-01-01", "2024-01-03")
