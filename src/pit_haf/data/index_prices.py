"""Field-specific VNINDEX vendor comparison; a close-only comparator never validates execution."""

import json
import re
from datetime import UTC, date, datetime, timedelta
from decimal import Context, Decimal, localcontext
from typing import Literal

from pydantic import Field, TypeAdapter, model_validator

from pit_haf.backtest.contracts import VN_OFFSET, Amount, Contract
from pit_haf.backtest.engine import literal
from pit_haf.data.market_prices import bad_constant, number, price, unique_object

PROTOCOL = "market_index_crosscheck_v0.1"
VIETCAP_URL = "https://trading.vietcap.com.vn/api/chart/OHLCChart/gap-chart"
FIELDS = ("open", "high", "low", "close", "volume")
SOURCE_FIELDS = dict(zip(FIELDS, ("o", "h", "l", "c", "v")))
AMOUNT = TypeAdapter(Amount)


class IndexPlan(Contract):
    protocol: Literal["market_index_crosscheck_v0.1"]
    start: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    end: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    symbol: Literal["VNINDEX"]
    count_back: Literal[1100]

    @model_validator(mode="after")
    def window(self):
        if not 0 <= (date.fromisoformat(self.end) - date.fromisoformat(self.start)).days <= 1461:
            raise ValueError("Index pilot requires an ordered window of at most 1461 days")
        return self


def request_body(plan):
    end = datetime.combine(
        date.fromisoformat(plan.end) + timedelta(days=1), datetime.min.time(), VN_OFFSET
    )
    return {
        "timeFrame": "ONE_DAY",
        "symbols": [plan.symbol],
        "to": int(end.timestamp()),
        "countBack": plan.count_back,
    }


def load(payload):
    if len(payload) > 8 * 1024 * 1024:
        raise ValueError("Index payload exceeds 8 MiB")
    return json.loads(
        payload, parse_float=Decimal, object_pairs_hook=unique_object, parse_constant=bad_constant
    )


def observations(rows, plan, source):
    if not 1 <= len(rows) <= 1500:
        raise ValueError("Require 1–1500 index observations")
    seen, retained, outside, invalid = set(), [], [], []
    for i, (day, source_time, row) in enumerate(rows, 1):
        date.fromisoformat(day)
        if day in seen:
            raise ValueError("Duplicate index session; no silent deduplication")
        seen.add(day)
        if not set(SOURCE_FIELDS.values()) <= set(row):
            raise ValueError("Missing index fields")
        values = {
            name: AMOUNT.validate_python(price(row[key]), strict=True)
            for name, key in SOURCE_FIELDS.items()
            if name != "volume"
        }
        volume = number(row["v"])
        if not 0 <= volume <= 10**12 or volume != volume.to_integral_value():
            raise ValueError("Index volume must be a nonnegative integer")
        values["volume"] = int(volume)
        if not plan.start <= day <= plan.end:
            outside.append(day)
            continue
        low, o, c, h = (Decimal(values[k]) for k in ("low", "open", "close", "high"))
        valid = low <= min(o, c) <= max(o, c) <= h
        if not valid:
            invalid.append({"session_date": day, "source_row": i, "reason": "OHLC_order_violation"})
        retained.append(
            {
                "session_date": day,
                "source_row": i,
                "source_time": source_time,
                **values,
                "ohlc_order_valid": valid,
                "available_at": None,
            }
        )
    if not retained:
        raise ValueError("No index observations inside the requested interval")
    return {
        "source": source,
        "symbol": plan.symbol,
        "asset_type": "index",
        "price_unit": "points",
        "raw_rows": len(rows),
        "outside_range_dates": sorted(outside),
        "observations": sorted(retained, key=lambda r: r["session_date"]),
        "ohlc_issues": sorted(invalid, key=lambda r: r["session_date"]),
        "historical_availability_validated": False,
        "eligible_for_execution": False,
    }


def kbs(payload, plan):
    data = load(payload)
    if (
        not isinstance(data, dict)
        or data.get("symbol") != plan.symbol
        or not isinstance(data.get("data_day"), list)
    ):
        raise ValueError("Expected KBS VNINDEX daily response")
    rows = []
    for row in data["data_day"]:
        if (
            not isinstance(row, dict)
            or not isinstance(row.get("t"), str)
            or not re.fullmatch(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}", row["t"])
        ):
            raise ValueError("Unsupported KBS index session label")
        day = datetime.strptime(row["t"], "%Y-%m-%d %H:%M").date().isoformat()
        rows.append((day, row["t"], row))
    return observations(rows, plan, "KBS")


def vietcap(payload, plan):
    data = load(payload)
    if isinstance(data, dict) and set(data) == {"data"}:
        data = data["data"]
    if (
        not isinstance(data, list)
        or len(data) != 1
        or not isinstance(data[0], dict)
        or data[0].get("symbol") != plan.symbol
    ):
        raise ValueError("Expected exactly one Vietcap VNINDEX series")
    series = data[0]
    fields = ("t", "o", "h", "l", "c", "v")
    if (
        any(not isinstance(series.get(k), list) for k in fields)
        or len({len(series[k]) for k in fields}) != 1
    ):
        raise ValueError("Vietcap index arrays must have equal lengths")
    if not 1 <= len(series["t"]) <= 1500:
        raise ValueError("Vietcap index row budget exceeded or response empty")
    rows = []
    for i, stamp in enumerate(series["t"]):
        if not isinstance(stamp, str) or not re.fullmatch(r"[1-2]\d{9}", stamp):
            raise ValueError("Expected explicit epoch-seconds string, never guess milliseconds")
        day = datetime.fromtimestamp(int(stamp), UTC).astimezone(VN_OFFSET).date().isoformat()
        rows.append((day, stamp, {k: series[k][i] for k in fields if k != "t"}))
    return observations(rows, plan, "Vietcap")


def comparator(rows):
    with localcontext(Context(prec=50)):
        first = Decimal(rows[0]["close"])
        previous = None
        peak = first
        drawdown = Decimal(0)
        curve = []
        for row in rows:
            close = Decimal(row["close"])
            peak = max(peak, close)
            drawdown = max(drawdown, 1 - close / peak)
            curve.append(
                {
                    "session_date": row["session_date"],
                    "close": row["close"],
                    "base_100": literal(100 * close / first),
                    "close_to_previous_return": literal(close / previous - 1)
                    if previous is not None
                    else None,
                }
            )
            previous = close
        return {
            "purpose": "Q2_close_only_price_comparator_development_diagnostic",
            "tradable": False,
            "first_observed_session": rows[0]["session_date"],
            "last_observed_session": rows[-1]["session_date"],
            "first_close": rows[0]["close"],
            "last_close": rows[-1]["close"],
            "sessions": len(rows),
            "observed_close_to_close_return": literal(previous / first - 1),
            "max_drawdown": literal(drawdown),
            "curve": curve,
            "fees": None,
            "macro_f1": None,
            "orders_generated": 0,
            "interpretation": "descriptive_observed_index_price_change; not_strategy_PnL_or_PiT_research_result",
        }


def compare(plan, left, right):
    # Recompute from source-decoded observations; no correction or vendor majority vote.
    for data, source in ((left, "KBS"), (right, "Vietcap")):
        if (
            data["source"] != source
            or data["symbol"] != plan.symbol
            or data["asset_type"] != "index"
            or data["price_unit"] != "points"
        ):
            raise ValueError(
                "Index comparison requires the requested vendors, identity and point units"
            )
    maps = [{r["session_date"]: r for r in n["observations"]} for n in (left, right)]
    left_dates, right_dates = map(set, maps)
    common = sorted(left_dates & right_dates)
    stats = {}
    mismatches = []
    with localcontext(Context(prec=50)):
        for field in FIELDS:
            differences = []
            for day in common:
                a, b = (maps[i][day][field] for i in (0, 1))
                delta = Decimal(a) - Decimal(b)
                if delta:
                    differences.append(abs(delta))
                    mismatches.append(
                        {
                            "session_date": day,
                            "field": field,
                            "KBS": a,
                            "Vietcap": b,
                            "KBS_minus_Vietcap": literal(delta),
                        }
                    )
            stats[field] = {
                "compared": len(common),
                "exact_matches": len(common) - len(differences),
                "differences": len(differences),
                "max_absolute_difference": literal(max(differences)) if differences else "0",
            }
    blockers = []
    if left_dates != right_dates:
        blockers.append("source_session_sets_differ")
    if len(common) < 2:
        blockers.append("fewer_than_two_common_sessions")
    if stats["close"]["differences"]:
        blockers.append("source_close_disagreement")
    agreed = not blockers
    return {
        "protocol": PROTOCOL,
        "kind": "real_index_vendor_comparison_diagnostic",
        "research_result": False,
        "symbol": plan.symbol,
        "price_unit": "points",
        "start": plan.start,
        "end": plan.end,
        "sources": [
            {
                "name": n["source"],
                "raw_rows": n["raw_rows"],
                "retained_rows": len(n["observations"]),
                "outside_range_count": len(n["outside_range_dates"]),
                "ohlc_issues": n["ohlc_issues"],
            }
            for n in (left, right)
        ],
        "common_sessions": len(common),
        "only_KBS": sorted(left_dates - right_dates),
        "only_Vietcap": sorted(right_dates - left_dates),
        "field_statistics": stats,
        "field_mismatches": sorted(mismatches, key=lambda r: (r["session_date"], r["field"])),
        "close_comparator_ready": agreed,
        "close_comparator_blockers": blockers,
        "close_comparator": comparator([maps[0][day] for day in common]) if agreed else None,
        "eligible_for_execution": False,
        "historical_availability_validated": False,
        "independent_gold": False,
        "limitations": [
            "vendor_endpoints_differ_but_upstream_lineage_independence_unverified",
            "OHLC_order_and_volume_differences_are_retained_not_repaired",
            "index_volume_semantics_not_aligned; raw_volume_differences_are_not_accuracy_scores",
            "cross_vendor_agreement_does_not_prove_exchange_calendar_or_historical_availability",
            "close_only_comparator_cannot_replace_open_execution_or_agent_horizon_labels",
        ],
    }
