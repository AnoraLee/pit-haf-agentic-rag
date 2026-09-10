"""Daily Vietnamese market data from Vnstock 4.0.7 / KBS.

This adapter validates data and units. Date filtering alone is NOT a complete
Point-in-Time guarantee: publication times and historical revisions still matter.
"""

import argparse
import re
from datetime import date, datetime, timedelta, timezone
from typing import Literal

import numpy as np
import pandas as pd

AssetType = Literal["equity", "index"]
PRICE_COLUMNS = ["open", "high", "low", "close"]
REQUIRED_COLUMNS = ["time", *PRICE_COLUMNS, "volume"]
VIETNAM_TZ = timezone(timedelta(hours=7))


class MarketDataError(ValueError):
    """Missing or invalid market data; never substitute a zero return."""


def _date_range(start: str, end: str) -> tuple[pd.Timestamp, pd.Timestamp]:
    for value in (start, end):
        if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
            raise ValueError("Dates must use YYYY-MM-DD.")
    first, last = date.fromisoformat(start), date.fromisoformat(end)
    if first > last:
        raise ValueError("start must be on or before end.")
    if last >= datetime.now(VIETNAM_TZ).date():
        raise ValueError("Use a past end date; today's daily bar may be incomplete.")
    return pd.Timestamp(first), pd.Timestamp(last)


def normalize_ohlcv(
    raw: pd.DataFrame, *, start: str, end: str, asset_type: AssetType
) -> pd.DataFrame:
    """Validate KBS bars, filter inclusive dates, and convert equity prices to VND.

    session_date is a daily bar label, NOT the time its close became available.
    This pure transformation does not make network requests or change raw.
    """
    first, last = _date_range(start, end)
    if asset_type not in ("equity", "index"):
        raise ValueError("asset_type must be equity or index.")
    if not isinstance(raw, pd.DataFrame) or raw.empty:
        raise MarketDataError("The source returned no rows.")
    if str(raw.attrs.get("source", "")).upper() != "KBS":
        raise MarketDataError("Expected KBS metadata; refusing an unknown price unit.")
    if not raw.columns.is_unique:
        raise MarketDataError("The source returned duplicate column names.")
    missing = set(REQUIRED_COLUMNS) - set(raw.columns)
    if missing:
        raise MarketDataError(f"Missing columns: {', '.join(sorted(missing))}.")

    frame = raw[REQUIRED_COLUMNS].copy()
    try:
        times = pd.to_datetime(frame.pop("time"), format="ISO8601", errors="raise")
        if times.isna().any():
            raise ValueError("Missing time")
        if times.dt.tz is not None:
            times = times.dt.tz_convert("Asia/Ho_Chi_Minh").dt.tz_localize(None)
        frame.insert(0, "session_date", times.dt.normalize())
    except (ValueError, TypeError, AttributeError) as exc:
        raise MarketDataError("Invalid daily bar dates.") from exc

    # Never invent weekend/holiday bars or forward-fill missing source data.
    frame = frame.loc[frame["session_date"].between(first, last)].copy()
    if frame.empty:
        raise MarketDataError("No rows fall within the requested dates.")
    if frame["session_date"].duplicated().any():
        raise MarketDataError("Multiple daily bars have the same session date.")

    numeric_columns = [*PRICE_COLUMNS, "volume"]
    try:
        frame[numeric_columns] = frame[numeric_columns].apply(pd.to_numeric)
    except (ValueError, TypeError) as exc:
        raise MarketDataError("OHLCV must contain numeric values.") from exc
    values = frame[numeric_columns].to_numpy(dtype=float, na_value=np.nan)
    if not np.isfinite(values).all():
        raise MarketDataError("OHLCV contains missing or infinite values.")
    if (frame[PRICE_COLUMNS] <= 0).any().any():
        raise MarketDataError("Prices must be positive.")
    if (frame["volume"] < 0).any() or (frame["volume"] % 1 != 0).any():
        raise MarketDataError("Volume must be a non-negative whole number.")
    if (
        (frame["low"] > frame[["open", "close"]].min(axis=1)).any()
        or (frame["high"] < frame[["open", "close"]].max(axis=1)).any()
    ):
        raise MarketDataError("OHLC prices violate low <= open/close <= high.")

    multiplier = 1000.0 if asset_type == "equity" else 1.0
    frame[PRICE_COLUMNS] = frame[PRICE_COLUMNS].astype(float) * multiplier
    frame["volume"] = frame["volume"].astype("int64")
    frame = frame.sort_values("session_date").reset_index(drop=True)
    frame.attrs = {
        "source": "KBS",
        "interval": "1D",
        "asset_type": asset_type,
        "price_unit": "VND" if asset_type == "equity" else "points",
        "source_price_unit": "1000 VND" if asset_type == "equity" else "points",
        "requested_start": start,
        "requested_end": end,
        "adjustment_status": "unknown",
        "time_semantics": "session label, not publication/availability time",
    }
    return frame


class VietnamMarketDataProvider:
    """One interface for 3-character equity tickers and the VNINDEX benchmark."""

    def get_prices(
        self, symbol: str, start: str, end: str, *, asset_type: AssetType = "equity"
    ) -> pd.DataFrame:
        _date_range(start, end)
        symbol = symbol.strip().upper()
        if asset_type == "equity":
            if not re.fullmatch(r"[A-Z][A-Z0-9]{2}", symbol):
                raise ValueError("Use an equity ticker such as FPT, HPG or VNM.")
        elif asset_type == "index":
            if symbol != "VNINDEX":
                raise ValueError("This first adapter supports only VNINDEX as index.")
        else:
            raise ValueError("asset_type must be equity or index.")

        raw = self._download(symbol, start, end, asset_type)
        reported_symbol = str(raw.attrs.get("symbol", "")).upper()
        if reported_symbol != symbol:
            raise MarketDataError(f"Source symbol mismatch: expected {symbol}.")
        frame = normalize_ohlcv(raw, start=start, end=end, asset_type=asset_type)
        frame.attrs.update(
            symbol=symbol,
            provider="vnstock",
            retrieved_at=datetime.now(timezone.utc).isoformat(),
        )
        return frame

    @staticmethod
    def _download(symbol: str, start: str, end: str, asset_type: AssetType) -> pd.DataFrame:
        # Lazy import lets offline tests run without initializing Vnstock services.
        from vnstock.ui import Market

        market = Market()
        asset = market.equity(symbol) if asset_type == "equity" else market.index(symbol)
        try:
            raw = asset.ohlcv(
                start=start, end=end, interval="1D", count=None, source="kbs"
            )
        except Exception as exc:
            raise MarketDataError(f"Could not download {symbol} from Vnstock/KBS.") from exc
        if not isinstance(raw, pd.DataFrame) or raw.empty:
            raise MarketDataError(f"Vnstock/KBS returned no data for {symbol}.")
        return raw


def main() -> None:
    parser = argparse.ArgumentParser(description="Check daily Vietnamese market data")
    parser.add_argument("--symbol", default="FPT")
    parser.add_argument("--asset-type", choices=["equity", "index"], default="equity")
    parser.add_argument("--start", required=True)
    parser.add_argument("--end", required=True)
    args = parser.parse_args()
    try:
        frame = VietnamMarketDataProvider().get_prices(
            args.symbol, args.start, args.end, asset_type=args.asset_type
        )
    except (MarketDataError, ValueError) as exc:
        parser.exit(1, f"Data error: {exc}\n")
    print(frame.head().to_string(index=False))
    print(f"Rows: {len(frame)}")
    print(f"Sessions: {frame['session_date'].min().date()} to {frame['session_date'].max().date()}")
    print(f"Metadata: {frame.attrs}")


if __name__ == "__main__":
    main()
