"""UI checks use labelled fixtures and make no market-data requests."""

from datetime import date
from pathlib import Path

import pandas as pd
from streamlit.testing.v1 import AppTest

from pit_haf.data.vnstock_provider import MarketDataError, VietnamMarketDataProvider

APP_PATH = Path(__file__).resolve().parents[1] / "app.py"


def sample_prices():
    frame = pd.DataFrame({
        "session_date": pd.to_datetime(["2024-01-02", "2024-01-03"]),
        "open": [100_000, 101_000], "high": [102_000, 103_000],
        "low": [99_000, 100_000], "close": [100_000, 102_000], "volume": [1000, 1200],
    })
    frame.attrs = {"source": "test-fixture", "adjustment_status": "unknown"}
    return frame


def test_initial_ui_uses_vietnam_and_does_not_download(monkeypatch):
    def unexpected(*args, **kwargs):
        raise AssertionError("No download until user clicks")
    monkeypatch.setattr(VietnamMarketDataProvider, "get_prices", unexpected)
    app = AppTest.from_file(APP_PATH).run()
    assert not app.exception
    assert app.text_input[0].value == "FPT"
    assert "Việt Nam" in app.title[0].value
    assert "chưa" in app.caption[0].value


def test_prices_are_displayed_as_vnd_without_claiming_backtest(monkeypatch):
    monkeypatch.setattr(VietnamMarketDataProvider, "get_prices", lambda *args, **kwargs: sample_prices())
    app = AppTest.from_file(APP_PATH).run()
    app.button[0].click().run()
    assert not app.exception
    assert app.metric[2].value == "+2.00%"
    assert app.metric[3].value == "102,000"
    assert "VND" in app.metric[3].label
    assert not app.success


def test_source_failure_is_visible_and_has_no_metrics(monkeypatch):
    def failed(*args, **kwargs):
        raise MarketDataError("source unavailable")
    monkeypatch.setattr(VietnamMarketDataProvider, "get_prices", failed)
    app = AppTest.from_file(APP_PATH).run()
    app.button[0].click().run()
    assert not app.exception
    assert "source unavailable" in app.error[0].value
    assert not app.metric


def test_index_is_requested_as_index_with_its_own_units(monkeypatch):
    calls = []
    def load(self, symbol, start, end, **kwargs):
        calls.append((symbol, kwargs))
        frame = sample_prices()
        if symbol == "VNINDEX":
            frame["close"] = [1200, 1210]
        return frame
    monkeypatch.setattr(VietnamMarketDataProvider, "get_prices", load)
    app = AppTest.from_file(APP_PATH).run()
    app.checkbox[0].check()
    app.button[0].click().run()
    assert not app.exception
    assert calls == [("FPT", {}), ("VNINDEX", {"asset_type": "index"})]
    assert any("điểm chỉ số" in heading.value for heading in app.subheader)


def test_invalid_range_stops_before_download(monkeypatch):
    def unexpected(*args, **kwargs):
        raise AssertionError("Invalid range must not call source")
    monkeypatch.setattr(VietnamMarketDataProvider, "get_prices", unexpected)
    app = AppTest.from_file(APP_PATH).run()
    app.date_input[0].set_value(date(2024, 7, 1))
    app.button[0].click().run()
    assert not app.exception
    assert "Ngày bắt đầu" in app.error[0].value
