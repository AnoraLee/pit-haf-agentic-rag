"""Hand accounting and timestamp boundary counterexamples; no market fixtures."""

import json
import subprocess
import sys
from decimal import ROUND_UP, Context, Decimal, localcontext
from pathlib import Path

import pytest

from pit_haf.backtest.contracts import ExecutionConfig, instant
from pit_haf.backtest.engine import simulate as legacy_simulate
from pit_haf.backtest.timed_contracts import TimedConfig, TimedScenario, settlement_schedule
from pit_haf.backtest.timed_engine import simulate
from pit_haf.backtest.timed_runner import demo, replay, run
from pit_haf.data.hub import file_sha
from pit_haf.llm.ollama import write_json

DATES = ["2022-08-24", "2022-08-25", "2022-08-26", "2022-08-29", "2022-08-30", "2022-08-31"]
TAIL = ["2022-09-01", "2022-09-05"]


def config(**updates):
    return TimedConfig.model_validate(
        {
            "protocol": "synthetic_timed_execution_v0.1",
            "initial_cash": "1000",
            "lot_size": 1,
            "buy_fee_bps": 0,
            "sell_fee_bps": 0,
            "slippage_bps": 0,
            "participation_bps": 10000,
            "share_lag_days": 2,
            "sale_cash_lag_days": 2,
            **updates,
        }
    )


def scenario(targets=None, *, symbols=None, count=6, share_time="13:00:00", cash_time="13:00:00"):
    symbols = symbols or ["SYN_A"]
    return TimedScenario.model_validate(
        {
            "market": {
                "kind": "synthetic_execution_diagnostic",
                "adjustment_status": "synthetic_no_corporate_actions",
                "calendar_basis": "explicit_synthetic_sessions",
                "currency": "scenario_units",
                "symbols": symbols,
                "sessions": [
                    {
                        "date": d,
                        "open_at": d + "T09:00:00+07:00",
                        "close_at": d + "T15:00:00+07:00",
                        "decision_at": d + "T16:00:00+07:00",
                    }
                    for d in DATES[:count]
                ],
                "bars": [
                    {
                        "session": d,
                        "symbol": s,
                        "open": "10",
                        "close": "10",
                        "high": "11",
                        "low": "9",
                        "volume": 10000,
                    }
                    for d in DATES[:count]
                    for s in symbols
                ],
                "targets": [
                    {"session": DATES[i], "weights": dict(zip(symbols, weights))}
                    for i, weights in (targets if targets is not None else [(0, ["1"])])
                ],
            },
            "settlement_basis": "explicit_synthetic_settlement_days",
            "settlement_days": [
                {
                    "date": d,
                    "shares_at": d + "T" + share_time + "+07:00",
                    "cash_at": d + "T" + cash_time + "+07:00",
                }
                for d in DATES + TAIL
            ],
        }
    )


def test_t_plus_two_afternoon_is_not_sellable_at_t_plus_two_open_unlike_integer_lag():
    data = scenario([(0, ["1"]), (2, ["0"]), (3, ["0"])])
    result = simulate(data, config())
    buy, blocked, sale = result["orders"]
    assert buy["execution_session"] == DATES[1]
    assert blocked["execution_session"] == DATES[3]
    assert blocked["status"] == "unfilled" and blocked["reasons"] == ["settled_shares"]
    assert result["equity_curve"][3]["positions"][0]["settled_quantity"] == 100
    assert sale["execution_session"] == DATES[4] and sale["filled_quantity"] == 100
    assert result["trades"][0]["settlement_available_at"] == DATES[3] + "T13:00:00+07:00"
    legacy = ExecutionConfig.model_validate(
        {
            **{
                k: v
                for k, v in config().model_dump().items()
                if k not in {"protocol", "share_lag_days", "sale_cash_lag_days"}
            },
            "protocol": "synthetic_execution_v0.1",
            "share_settlement_sessions": 2,
            "sale_cash_settlement_sessions": 2,
        }
    )
    assert legacy_simulate(data.market, legacy)["orders"][1]["filled_quantity"] == 100
    assert result["metrics"]["ending_equity"] == "1000"
    assert result["ending_receivables"][0]["available_at"] == TAIL[0] + "T13:00:00+07:00"


@pytest.mark.parametrize(
    "cash_time,buys", [("09:00:00", 2), ("09:00:00.000001", 1), ("13:00:00", 1)]
)
def test_same_day_cash_can_fund_next_symbol_only_at_or_before_open(cash_time, buys):
    result = simulate(
        scenario(
            [(0, ["1", "0"]), (1, ["0", "1"])],
            symbols=["SYN_A", "SYN_B"],
            count=3,
            cash_time=cash_time,
        ),
        config(share_lag_days=0, sale_cash_lag_days=0),
    )
    assert sum(t["side"] == "buy" for t in result["trades"]) == buys
    assert result["equity_curve"][-1]["equity"] == "1000"
    if buys == 1:
        assert result["orders"][-1]["reasons"] == ["available_cash"]
        assert result["equity_curve"][-1]["available_cash"] == "1000"
    cash_event = next(e for e in result["settlement_events"] if e["event"] == "sale_cash_released")
    assert cash_event["at"] == DATES[2] + "T" + cash_time + "+07:00"
    assert instant(cash_event["observed_at"]) >= instant(cash_event["at"])


@pytest.mark.parametrize(
    "time,quantity", [("09:00:00", 100), ("09:00:00.000001", 0), ("13:00:00", 0)]
)
def test_stock_release_boundary_is_inclusive_without_rounding_seconds(time, quantity):
    result = simulate(scenario([(0, ["1"]), (2, ["0"])], share_time=time), config())
    assert result["orders"][-1]["filled_quantity"] == quantity


def test_settlement_days_are_distinct_from_trading_days_and_no_days_are_generated():
    data = scenario().model_dump()
    # Remove a trading session while retaining it as an explicit settlement day.
    data["market"]["sessions"].pop(2)
    data["market"]["bars"].pop(2)
    data = TimedScenario.model_validate(data)
    row = settlement_schedule(data, config())[1]
    assert row["trade_session"] == DATES[1] and row["share_settlement_date"] == DATES[3]
    result = simulate(data, config())
    assert [r["session"] for r in result["equity_curve"]] == [d for d in DATES if d != DATES[2]]
    # Monday + two explicit settlement days remains Wednesday despite the trading gap.
    assert settlement_schedule(data, config())[2]["share_settlement_date"] == DATES[5]


def test_release_time_is_selected_on_settlement_date_across_timing_change():
    data = scenario().model_dump()
    for day in data["settlement_days"]:
        if day["date"] < "2022-08-29":
            day["shares_at"] = day["date"] + "T16:00:00+07:00"
            day["cash_at"] = day["date"] + "T16:00:00+07:00"
    rows = settlement_schedule(TimedScenario.model_validate(data), config())
    assert rows[0]["shares_available_at"] == "2022-08-26T16:00:00+07:00"
    assert rows[1]["shares_available_at"] == "2022-08-29T13:00:00+07:00"
    assert rows[1]["sale_cash_available_at"] == rows[1]["shares_available_at"]


@pytest.mark.parametrize(
    "time,close_cash,ending_cash",
    [
        ("15:00:00", "1000", "1000"),
        ("15:30:00", "0", "1000"),
        ("16:00:00", "0", "1000"),
        ("16:00:00.000001", "0", "0"),
    ],
)
def test_close_snapshot_does_not_include_post_close_release(time, close_cash, ending_cash):
    result = simulate(
        scenario([(0, ["1"]), (1, ["0"])], count=3, cash_time=time),
        config(share_lag_days=0, sale_cash_lag_days=0),
    )
    close = result["equity_curve"][-1]
    assert close["available_cash"] == close_cash
    assert close["unsettled_sale_cash"] == str(1000 - int(close_cash))
    assert close["equity"] == "1000"
    assert result["ending_available_cash"] == ending_cash
    assert result["state_at"] == DATES[2] + "T16:00:00+07:00"


def test_settlement_only_day_releases_keep_actual_date_and_observation_time():
    data = scenario([(0, ["1"]), (1, ["0"])], count=4).model_dump()
    # Sell on Friday; cash release on an explicit Saturday settlement-only fixture day.
    data["settlement_days"].insert(
        3,
        {
            "date": "2022-08-27",
            "shares_at": "2022-08-27T13:00:00+07:00",
            "cash_at": "2022-08-27T13:00:00+07:00",
        },
    )
    result = simulate(
        TimedScenario.model_validate(data), config(share_lag_days=0, sale_cash_lag_days=1)
    )
    released = result["cash_ledger"][-1]
    assert released["session"] == "2022-08-27"
    assert released["at"] == "2022-08-27T13:00:00+07:00"
    assert released["observed_at"] == DATES[3] + "T09:00:00+07:00"
    assert result["equity_curve"][2]["unsettled_sale_cash"] == "1000"
    assert result["equity_curve"][3]["available_cash"] == "1000"


def test_round_trip_fees_slippage_fifo_and_partial_settled_lots_conserve_value():
    data = scenario([(0, ["0.5"]), (1, ["1"]), (3, ["0"])])
    result = simulate(data, config(buy_fee_bps=100, sell_fee_bps=200))
    sale = result["orders"][-1]
    # Buy 50 then 49, first lot available on Monday, second only Tuesday afternoon.
    assert sale["requested_quantity"] == 99 and sale["filled_quantity"] == 50
    assert sale["status"] == "partial" and sale["reasons"] == ["settled_shares"]
    assert result["metrics"]["fees_paid"] == "19.9"
    assert result["metrics"]["ending_equity"] == "980.1"
    assert result["ending_lots"][0]["quantity"] == 49
    for row in result["equity_curve"]:
        assert Decimal(row["equity"]) == (
            Decimal(row["available_cash"])
            + Decimal(row["unsettled_sale_cash"])
            + sum(Decimal(p["market_value"]) for p in row["positions"])
        )
    assert all(Decimal(r["cash_after"]) >= 0 for r in result["cash_ledger"])
    assert result["metrics"]["macro_f1"] is None and result["research_result"] is False


def test_sale_cash_released_at_t_plus_two_noon_cannot_fund_that_open_or_auto_retry():
    data = scenario(
        [(0, ["1", "0"]), (1, ["0", "1"]), (3, ["0", "1"]), (4, ["0", "1"])],
        symbols=["SYN_A", "SYN_B"],
    )
    result = simulate(data, config(share_lag_days=0))
    assert [(t["session"], t["symbol"], t["side"]) for t in result["trades"]] == [
        (DATES[1], "SYN_A", "buy"),
        (DATES[2], "SYN_A", "sell"),
        (DATES[5], "SYN_B", "buy"),
    ]
    # Friday sale settles Tuesday noon, not Tuesday open; fresh Wednesday target is needed.
    assert result["equity_curve"][3]["unsettled_sale_cash"] == "1000"
    assert result["equity_curve"][4]["available_cash"] == "1000"
    assert result["orders"][-2]["filled_quantity"] == 0
    assert result["orders"][-1]["filled_quantity"] == 100
    no_retry = scenario([(0, ["1", "0"]), (1, ["0", "1"])], symbols=["SYN_A", "SYN_B"])
    assert len(simulate(no_retry, config(share_lag_days=0))["trades"]) == 2


def test_timed_execution_preserves_lot_volume_and_adverse_price_guards():
    data = scenario(count=2).model_dump()
    data["market"]["bars"][1]["volume"] = 37
    result = simulate(
        TimedScenario.model_validate(data),
        config(lot_size=10, participation_bps=5000, slippage_bps=100),
    )
    trade = result["trades"][0]
    assert trade["quantity"] == 10 and trade["price"] == "10.1"
    assert trade["slippage_cost"] == "1"
    assert result["orders"][0]["reasons"] == ["volume_cap", "available_cash"]
    data["market"]["bars"][1].update(low="10", high="10")
    blocked = simulate(TimedScenario.model_validate(data), config(slippage_bps=100))
    assert blocked["trades"] == [] and blocked["settlement_events"] == []
    assert "outside_bar_range" in blocked["orders"][0]["reasons"]


def test_timezone_instants_and_decimal_context_do_not_change_execution():
    data = scenario().model_dump()
    expected = simulate(TimedScenario.model_validate(data), config(slippage_bps=1))
    for day in data["settlement_days"]:
        day["shares_at"] = day["date"] + "T06:00:00Z"
    with localcontext(Context(prec=6, rounding=ROUND_UP)):
        result = simulate(TimedScenario.model_validate(data), config(slippage_bps=1))
    assert result["orders"] == expected["orders"]
    assert result["metrics"] == expected["metrics"]
    assert result["equity_curve"] == expected["equity_curve"]


@pytest.mark.parametrize(
    "change",
    [
        "missing_trading_day",
        "duplicate_day",
        "unsorted",
        "invalid_date",
        "naive",
        "wrong_date",
        "no_tail",
        "before_trade",
        "mutated_market",
        "unknown_basis",
    ],
)
def test_bad_or_incomplete_calendars_fail_before_output_creation(tmp_path, change):
    data = scenario().model_dump()
    cfg = config()
    if change == "missing_trading_day":
        data["settlement_days"].pop(1)
    elif change == "duplicate_day":
        data["settlement_days"].insert(1, data["settlement_days"][0])
    elif change == "unsorted":
        data["settlement_days"].reverse()
    elif change == "invalid_date":
        data["settlement_days"][0]["date"] = "2022-02-30"
    elif change == "naive":
        data["settlement_days"][0]["shares_at"] = "2022-08-24T13:00:00"
    elif change == "wrong_date":
        data["settlement_days"][0]["cash_at"] = "2022-08-25T13:00:00+07:00"
    elif change == "no_tail":
        data["settlement_days"] = data["settlement_days"][:-2]
    elif change == "before_trade":
        cfg = config(share_lag_days=0)
        data["settlement_days"][0]["shares_at"] = "2022-08-24T08:59:59+07:00"
    elif change == "mutated_market":
        data["market"]["targets"][0]["weights"]["SYN_A"] = "1.1"
    else:
        data["settlement_basis"] = "verified_HOSE"
    with pytest.raises(ValueError):
        run(tmp_path, json.dumps(data).encode(), cfg.model_dump_json().encode())
    assert not (tmp_path / "outputs").exists()


def test_simulate_revalidates_nested_mutation_and_rejects_boolean_lag():
    data = scenario()
    data.settlement_days.pop()
    with pytest.raises(ValueError, match="tail"):
        simulate(data, config())
    for update in [{"share_lag_days": True}, {"sale_cash_lag_days": -1}, {"initial_cash": "0"}]:
        with pytest.raises(ValueError):
            config(**update)


def test_future_price_changes_do_not_affect_prior_orders_or_settlement_schedule():
    original = scenario()
    changed = original.model_dump()
    changed["market"]["bars"][-1].update(open="100", high="101", low="89", close="90")
    before, after = (
        simulate(original, config()),
        simulate(TimedScenario.model_validate(changed), config()),
    )
    assert before["orders"] == after["orders"]
    assert before["settlement_schedule"] == after["settlement_schedule"]
    assert before["equity_curve"][:-1] == after["equity_curve"][:-1]


def test_run_replay_and_all_cash_csv_headers_preserve_exact_input_bytes(tmp_path):
    raw = b" \n" + scenario(targets=[]).model_dump_json().encode()
    cfg = config().model_dump_json().encode() + b"\r\n"
    folder, result = run(tmp_path, raw, cfg)
    assert replay(tmp_path, folder) == result
    assert (folder / "original.json").read_bytes() == raw
    assert (folder / "config.json").read_bytes() == cfg
    assert result["settlement_events"] == result["trades"] == []
    assert result["metrics"]["net_return"] == "0"
    for name in ["trades.csv", "settlement_events.csv"]:
        assert len((folder / name).read_text().splitlines()) == 1
    assert (folder / "settlement_schedule.csv").read_text().startswith("trade_session,trade_at,")
    assert not (tmp_path / "data").exists()


@pytest.mark.parametrize(
    "change", ["result", "csv", "schedule_csv", "scenario", "manifest", "raw", "file_set"]
)
def test_reseal_does_not_hide_derived_result_or_provenance_tampering(tmp_path, change):
    folder, _ = run(
        tmp_path, demo().model_dump_json().encode(), config().model_dump_json().encode()
    )
    if change == "result":
        result = json.loads((folder / "result.json").read_bytes())
        result["settlement_events"] = []
        write_json(folder / "result.json", result)
    elif change in {"csv", "schedule_csv"}:
        (
            folder / ("settlement_events.csv" if change == "csv" else "settlement_schedule.csv")
        ).write_bytes(b"forged\n")
    elif change == "scenario":
        data = json.loads((folder / "scenario.json").read_bytes())
        data["settlement_days"][3]["shares_at"] = (
            data["settlement_days"][3]["date"] + "T09:00:00+07:00"
        )
        write_json(folder / "scenario.json", data)
        manifest = json.loads((folder / "manifest.json").read_bytes())
        manifest["scenario_sha256"] = file_sha(folder / "scenario.json")
        write_json(folder / "manifest.json", manifest)
    elif change == "manifest":
        manifest = json.loads((folder / "manifest.json").read_bytes())
        manifest["research_result"] = True
        write_json(folder / "manifest.json", manifest)
    elif change == "raw":
        (folder / "config.json").write_bytes(b"{}")
    else:
        (folder / "unexpected.txt").write_bytes(b"extra")
    if change != "raw":
        write_json(
            folder / "integrity.json",
            {
                "files": {
                    p.name: file_sha(p) for p in folder.iterdir() if p.name != "integrity.json"
                }
            },
        )
    with pytest.raises(ValueError, match="differ|Incomplete"):
        replay(tmp_path, folder)


@pytest.mark.parametrize("raw", [b'{"a":1,"a":2}', b'{"a":NaN}', b'{"a":Infinity}'])
def test_noncanonical_json_is_rejected(tmp_path, raw):
    with pytest.raises(ValueError):
        run(tmp_path, raw, config().model_dump_json().encode())


def test_cli_q1_replay_and_override_and_external_path_rejection(tmp_path):
    cfg = tmp_path / "config.json"
    cfg.write_text(config().model_dump_json(), encoding="utf-8")
    cmd = [
        sys.executable,
        "-X",
        "utf8",
        "-m",
        "pit_haf.backtest.timed_runner",
        "--root",
        str(tmp_path),
    ]
    output = subprocess.run(
        [*cmd, "--demo", "--config", str(cfg), "--baseline", "Q1", "--rebalance-every", "2"],
        capture_output=True,
        check=True,
    )
    saved = json.loads(output.stdout)
    assert saved["research_result"] is False and Path(saved["path"]).is_dir()
    replayed = subprocess.run([*cmd, "--replay", saved["path"]], capture_output=True, check=True)
    assert json.loads(replayed.stdout) == saved
    rejected = subprocess.run(
        [*cmd, "--replay", saved["path"], "--config", str(cfg)], capture_output=True
    )
    assert rejected.returncode == 2 and b"omit overrides" in rejected.stderr
    with pytest.raises(ValueError):
        replay(tmp_path, tmp_path)
