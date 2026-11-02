"""Decode public KBS daily response bytes, preserving decimal prices and unknown availability."""

import json
import re
from datetime import date, datetime
from decimal import Context, Decimal, localcontext
from typing import Literal
from urllib.parse import urlencode

from pydantic import Field, model_validator

from pit_haf.backtest.contracts import Bar, Contract

HOST = "kbbuddywts.kbsec.com.vn"
BASE = f"https://{HOST}/iis-server/investment"
PROTOCOL = "market_price_snapshot_v0.1"


class Instrument(Contract):
    symbol: str = Field(pattern=r"^[A-Z][A-Z0-9]{2,11}$")
    asset_type: Literal["equity", "index"]

    @model_validator(mode="after")
    def identity(self):
        if (self.asset_type == "equity" and not re.fullmatch(r"[A-Z][A-Z0-9]{2}", self.symbol)) or (
            self.asset_type == "index" and self.symbol != "VNINDEX"
        ):
            raise ValueError("Use a three-character equity or the VNINDEX comparator")
        return self


class CapturePlan(Contract):
    protocol: Literal["market_price_snapshot_v0.1"]
    start: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    end: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    instruments: list[Instrument] = Field(min_length=1, max_length=4)

    @model_validator(mode="after")
    def request_window(self):
        first, last = date.fromisoformat(self.start), date.fromisoformat(self.end)
        if not 0 <= (last - first).days <= 1461:
            raise ValueError("Price pilot requires an ordered window of at most four years")
        symbols = [i.symbol for i in self.instruments]
        if len(symbols) != len(set(symbols)):
            raise ValueError("Duplicate requested instrument")
        return self


def source_url(plan, instrument):
    group = "stocks" if instrument.asset_type == "equity" else "index"
    params = {
        "sdate": date.fromisoformat(plan.start).strftime("%d-%m-%Y"),
        "edate": date.fromisoformat(plan.end).strftime("%d-%m-%Y"),
    }
    return f"{BASE}/{group}/{instrument.symbol}/data_day?{urlencode(params)}"


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON field in market response")
        result[key] = value
    return result


def bad_constant(value):
    raise ValueError("Non-finite JSON market number")


def number(value):
    if type(value) is int:
        return Decimal(value)
    if isinstance(value, Decimal) and value.is_finite():
        return value
    raise ValueError("Market numbers must be finite JSON numbers, not booleans or guessed strings")


def price(value):
    value = number(value)
    if not Decimal("0.000001") <= value <= Decimal("999999999999999999.999999"):
        raise ValueError("Market price is outside supported positive precision/range")
    text = format(value, "f")
    return text.rstrip("0").rstrip(".") if "." in text else text


def decode(payload: bytes, plan: CapturePlan, instrument: Instrument):
    if len(payload) > 8 * 1024 * 1024:
        raise ValueError("Market response exceeds 8 MiB budget")
    data = json.loads(
        payload, parse_float=Decimal, object_pairs_hook=unique_object, parse_constant=bad_constant
    )
    if not isinstance(data, dict) or data.get("symbol") != instrument.symbol:
        raise ValueError("Market response symbol differs from requested instrument")
    rows = data.get("data_day")
    if not isinstance(rows, list) or not 1 <= len(rows) <= 2000:
        raise ValueError("Require 1–2000 daily source rows")
    seen, bars, outside = set(), [], []
    for row in rows:
        if not isinstance(row, dict) or not {"t", "o", "h", "l", "c", "v"} <= set(row):
            raise ValueError("Market response is missing daily OHLCV fields")
        stamp = row["t"]
        if not isinstance(stamp, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}", stamp):
            raise ValueError(
                "Unsupported source bar timestamp; do not infer its timezone or availability"
            )
        parsed = datetime.strptime(stamp, "%Y-%m-%d %H:%M")
        day = parsed.date().isoformat()
        if day in seen:
            raise ValueError("Duplicate source session; never choose one row silently")
        seen.add(day)
        volume = number(row["v"])
        if not 0 <= volume <= 10**12 or volume != volume.to_integral_value():
            raise ValueError("Source volume must be a nonnegative whole number")
        # The installed KBS adapter divides raw equity prices by 1000; these
        # response bytes already carry full VND. Index values stay in points.
        bar = Bar(
            session=day,
            symbol=instrument.symbol,
            open=price(row["o"]),
            high=price(row["h"]),
            low=price(row["l"]),
            close=price(row["c"]),
            volume=int(volume),
        )
        if not plan.start <= day <= plan.end:
            outside.append(day)
            continue
        bars.append(
            {
                "session_date": day,
                "source_time": stamp,
                **{k: v for k, v in bar.model_dump().items() if k not in {"session", "symbol"}},
                "available_at": None,
            }
        )
    if not bars:
        raise ValueError("No source rows fall inside the requested interval")
    bars.sort(key=lambda b: b["session_date"])
    return {
        "symbol": instrument.symbol,
        "asset_type": instrument.asset_type,
        "source_url": source_url(plan, instrument),
        "price_unit": "VND" if instrument.asset_type == "equity" else "points",
        "unit_basis": "installed_vnstock_4.0.7_KBS_adapter_mapping; not_independent_exchange_validation",
        "adjustment_status": "unknown",
        "historical_availability_validated": False,
        "time_semantics": "source_naive_daily_label_preserved; not_publication_or_open_execution_time",
        "source_rows": len(rows),
        "outside_range_dates": sorted(outside),
        "bars": bars,
        "sessions_by_year": {
            year: sum(b["session_date"].startswith(year) for b in bars)
            for year in sorted({b["session_date"][:4] for b in bars})
        },
        "weekend_dates": [
            b["session_date"] for b in bars if date.fromisoformat(b["session_date"]).weekday() >= 5
        ],
        "zero_volume_dates": [b["session_date"] for b in bars if b["volume"] == 0],
    }


def audit(plan, captured):
    successful = [entry["normalized"] for entry in captured if entry.get("normalized") is not None]
    index = next((n for n in successful if n["asset_type"] == "index"), None)
    index_dates = {b["session_date"] for b in index["bars"]} if index else None
    assets = []
    with localcontext(Context(prec=50)):
        for n in successful:
            dates = {b["session_date"] for b in n["bars"]}
            assets.append(
                {
                    "symbol": n["symbol"],
                    "asset_type": n["asset_type"],
                    "price_unit": n["price_unit"],
                    "rows": len(n["bars"]),
                    "first_session": min(dates),
                    "last_session": max(dates),
                    "sessions_by_year": n["sessions_by_year"],
                    "zero_volume_count": len(n["zero_volume_dates"]),
                    "weekend_dates": n["weekend_dates"],
                    "outside_range_count": len(n["outside_range_dates"]),
                    "missing_vs_observed_index": sorted(index_dates - dates)
                    if index_dates is not None
                    else None,
                    "extra_vs_observed_index": sorted(dates - index_dates)
                    if index_dates is not None
                    else None,
                    "adjustment_status": "unknown",
                    "eligible_for_execution": False,
                }
            )
    return {
        "protocol": PROTOCOL,
        "kind": "real_market_snapshot_quality_diagnostic",
        "research_result": False,
        "requested_start": plan.start,
        "requested_end": plan.end,
        "requested_instruments": len(plan.instruments),
        "successful_instruments": len(successful),
        "failed_instruments": len(captured) - len(successful),
        "assets": assets,
        "failures": [
            {"symbol": e["symbol"], "error": e["error"]}
            for e in captured
            if e.get("normalized") is None
        ],
        "calendar_basis": "observed_index_sessions_same_source; not_independent_exchange_calendar"
        if index
        else "unverified",
        "eligible_for_execution": False,
        "historical_availability_validated": False,
        "independent_gold": False,
        "blockers": [
            "adjustment_recipe_and_corporate_actions_unverified",
            "independent_venue_calendar_missing",
            "historical_bar_availability_and_revision_proof_missing",
            "execution_rules_by_period_unverified",
            "synthetic_engine_does_not_model_intraday_settlement_or_real_market_execution",
        ],
        "index_policy": "VNINDEX_is_a_points_comparator_not_a_tradable_equity",
        "new_llm_calls": 0,
        "strategy_returns_computed": False,
    }
