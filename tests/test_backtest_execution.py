"""Hand-calculated synthetic accounting and temporal/settlement counterexamples."""

import json
import subprocess
import sys
from decimal import ROUND_UP, Context, Decimal, localcontext
from pathlib import Path

import pytest

from pit_haf.backtest.baselines import schedule
from pit_haf.backtest.contracts import ExecutionConfig, Scenario
from pit_haf.backtest.engine import simulate
from pit_haf.backtest.runner import demo, replay, run
from pit_haf.data.hub import file_sha
from pit_haf.llm.ollama import write_json

DATES = ["2024-01-02", "2024-01-03", "2024-01-05", "2024-01-08", "2024-01-09", "2024-01-11"]


def config(**updates):
    return ExecutionConfig.model_validate(
        {
            "protocol": "synthetic_execution_v0.1",
            "initial_cash": "1000",
            "lot_size": 1,
            "buy_fee_bps": 0,
            "sell_fee_bps": 0,
            "slippage_bps": 0,
            "participation_bps": 10000,
            "share_settlement_sessions": 0,
            "sale_cash_settlement_sessions": 0,
            **updates,
        }
    )


def scenario(targets=None, *, symbols=None, prices=None, count=6, volume=10000):
    symbols = symbols or ["SYN_A"]
    bars = []
    for i, d in enumerate(DATES[:count]):
        for s in symbols:
            o, c = (prices or {}).get((i, s), (10, 10))
            bars.append(
                {
                    "session": d,
                    "symbol": s,
                    "open": str(o),
                    "high": str(max(o, c) + 1),
                    "low": str(min(o, c) - 1),
                    "close": str(c),
                    "volume": volume,
                }
            )
    return Scenario.model_validate(
        {
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
            "bars": bars,
            "targets": [
                {"session": DATES[i], "weights": dict(zip(symbols, weights))}
                for i, weights in (targets or [(0, ["1"])])
            ],
        }
    )


def test_signal_uses_close_then_next_supplied_open_with_cash_limited_gap_and_no_forced_exit():
    data = scenario([(0, ["1"]), (2, ["0"])], count=3, prices={(1, "SYN_A"): (20, 20)})
    result = simulate(data, config())
    first, last = result["orders"]
    assert first["signal_session"] == DATES[0] and first["execution_session"] == DATES[1]
    assert first["sizing_close"] == "10" and first["open_reference"] == "20"
    assert first["requested_quantity"] == 100 and first["filled_quantity"] == 50
    assert first["status"] == "partial" and first["reasons"] == ["available_cash"]
    assert last["status"] == "expired" and last["reasons"] == ["no_next_session"]
    assert len(result["trades"]) == 1 and result["equity_curve"][0]["positions"][0]["quantity"] == 0
    assert result["equity_curve"][-1]["positions"][0]["quantity"] == 50
    # Friday -> Monday uses the supplied calendar; no generated weekend bars.
    friday = simulate(scenario([(2, ["1"])], count=4), config())
    assert friday["trades"][0]["session"] == "2024-01-08"


def test_round_trip_matches_hand_accounting_with_fees_and_cash_conservation():
    result = simulate(
        scenario(
            [(0, ["1"]), (1, ["0"])],
            count=3,
            prices={(1, "SYN_A"): (10, 12), (2, "SYN_A"): (11, 11)},
        ),
        config(buy_fee_bps=100, sell_fee_bps=200),
    )
    assert [(t["side"], t["quantity"], t["fee"]) for t in result["trades"]] == [
        ("buy", 99, "9.9"),
        ("sell", 99, "21.78"),
    ]
    assert result["metrics"]["ending_equity"] == "1067.32"
    assert result["metrics"]["net_return"] == "0.06732"
    assert result["metrics"]["fees_paid"] == "31.68"
    assert sum(Decimal(row["amount"]) for row in result["cash_ledger"]) == Decimal("1067.32")
    assert float(result["metrics"]["max_drawdown"]) == pytest.approx(120.78 / 1188.1, abs=1e-14)
    assert float(result["metrics"]["two_sided_turnover"]) == pytest.approx(
        2079 / ((1000 + 1188.1 + 1067.32) / 3), abs=1e-14
    )
    for row in result["equity_curve"]:
        assert Decimal(row["equity"]) == Decimal(row["available_cash"]) + Decimal(
            row["unsettled_sale_cash"]
        ) + sum(Decimal(p["market_value"]) for p in row["positions"])


def test_adverse_slippage_is_separate_from_fees_and_open_reference():
    result = simulate(scenario([(0, ["1"]), (1, ["0"])], count=3), config(slippage_bps=100))
    assert [(t["price"], t["quantity"]) for t in result["trades"]] == [("10.1", 99), ("9.9", 99)]
    assert result["metrics"]["slippage_cost"] == "19.8" and result["metrics"]["fees_paid"] == "0"
    assert result["metrics"]["ending_equity"] == "980.2"


def test_execution_does_not_invent_a_price_outside_supplied_ohlc():
    data = scenario(count=2).model_dump()
    data["bars"][1].update(high="10", low="10")
    result = simulate(Scenario.model_validate(data), config(slippage_bps=1))
    assert result["trades"] == []
    assert set(result["orders"][0]["reasons"]) == {"outside_bar_range", "available_cash"}
    assert result["metrics"]["unfilled_orders"] == 1
    assert result["metrics"]["partially_filled_orders"] == 0


def test_unsettled_final_sale_is_a_receivable_not_available_cash_or_lost_nav():
    result = simulate(
        scenario([(0, ["1"]), (1, ["0"])], count=3), config(sale_cash_settlement_sessions=2)
    )
    assert result["equity_curve"][-1]["available_cash"] == "0"
    assert result["equity_curve"][-1]["unsettled_sale_cash"] == "1000"
    assert result["metrics"]["ending_equity"] == "1000"
    assert result["ending_receivables"][0]["release_index"] == 4


def test_settlement_blocks_sale_then_reinvestment_until_release_without_losing_nav():
    data = scenario(
        [(0, ["1", "0"]), (1, ["0", "1"]), (2, ["0", "1"]), (3, ["0", "1"])],
        symbols=["SYN_A", "SYN_B"],
    )
    result = simulate(data, config(share_settlement_sessions=2, sale_cash_settlement_sessions=1))
    assert [(t["session"], t["symbol"], t["side"]) for t in result["trades"]] == [
        (DATES[1], "SYN_A", "buy"),
        (DATES[3], "SYN_A", "sell"),
        (DATES[4], "SYN_B", "buy"),
    ]
    assert result["equity_curve"][3]["unsettled_sale_cash"] == "1000"
    assert result["equity_curve"][3]["available_cash"] == "0"
    assert all(row["equity"] == "1000" for row in result["equity_curve"])
    assert any(o["reasons"] == ["settled_shares"] for o in result["orders"])
    assert result["ending_lots"][0]["release_index"] == 6


def test_partial_settled_inventory_uses_fifo_and_pending_orders_do_not_retry():
    result = simulate(
        scenario([(0, ["0.5"]), (1, ["1"]), (2, ["0"])], count=5),
        config(share_settlement_sessions=2),
    )
    sell = result["orders"][-1]
    assert sell["requested_quantity"] == 100 and sell["filled_quantity"] == 50
    assert sell["status"] == "partial" and sell["reasons"] == ["settled_shares"]
    assert result["equity_curve"][-1]["positions"][0]["quantity"] == 50
    # No new target on the next day means no retry when the other lot settles.
    assert len(result["orders"]) == 3


@pytest.mark.parametrize("volume,expected", [(0, 0), (9, 0), (25, 20), (10000, 100)])
def test_volume_caps_round_down_to_lots_without_filling_zero_volume(volume, expected):
    result = simulate(scenario(count=2, volume=volume), config(lot_size=10))
    assert result["orders"][0]["filled_quantity"] == expected
    assert all(t["quantity"] % 10 == 0 for t in result["trades"])


def test_fixed_alphabetical_allocation_is_input_bar_order_invariant():
    data = scenario([(0, ["0.5", "0.5"])], symbols=["SYN_A", "SYN_B"], count=2)
    settings = config(buy_fee_bps=100)
    result = simulate(data, settings)
    reversed_data = Scenario.model_validate(
        {**data.model_dump(), "bars": list(reversed(data.model_dump()["bars"]))}
    )
    assert simulate(reversed_data, settings) == result
    assert [(t["symbol"], t["quantity"]) for t in result["trades"]] == [
        ("SYN_A", 50),
        ("SYN_B", 49),
    ]


def test_future_bar_perturbation_preserves_earlier_orders_and_equity():
    data = scenario([(0, ["1"]), (4, ["0"])])
    first = simulate(data, config())
    changed = data.model_dump()
    changed["bars"][-1].update(open="100", close="80", high="101", low="79")
    second = simulate(Scenario.model_validate(changed), config())
    assert first["equity_curve"][:-1] == second["equity_curve"][:-1]
    assert first["orders"][0] == second["orders"][0]
    assert first["orders"][-1]["requested_quantity"] == second["orders"][-1]["requested_quantity"]
    assert first["metrics"]["ending_equity"] != second["metrics"]["ending_equity"]


def test_ambient_decimal_context_cannot_change_results_weights_or_overweight_validation():
    data = scenario(symbols=["SYN_A", "SYN_B", "SYN_C"], targets=[(0, ["1", "0", "0"])])
    expected = simulate(schedule(data, "Q0"), config())
    invalid = data.model_dump()
    invalid["targets"][0]["weights"] = {"SYN_A": "0.50000001", "SYN_B": "0.5", "SYN_C": "0"}
    with localcontext(Context(prec=6, rounding=ROUND_UP)):
        assert simulate(schedule(data, "Q0"), config()) == expected
        with pytest.raises(ValueError, match="summing"):
            Scenario.model_validate(invalid)


@pytest.mark.parametrize(
    "change",
    [
        "missing_bar",
        "duplicate_bar",
        "unknown_symbol",
        "missing_target_symbol",
        "overweight",
        "duplicate_target",
        "naive_time",
        "decision_after_next_open",
        "invalid_ohlc",
        "unknown_adjustment",
        "research_kind",
        "boolean_volume",
    ],
)
def test_invalid_or_unverified_inputs_fail_closed(change):
    data = scenario().model_dump()
    if change == "missing_bar":
        data["bars"].pop()
    if change == "duplicate_bar":
        data["bars"].append(data["bars"][0])
    if change == "unknown_symbol":
        data["bars"][0]["symbol"] = "UNKNOWN"
    if change == "missing_target_symbol":
        data["targets"][0]["weights"] = {}
    if change == "overweight":
        data["targets"][0]["weights"]["SYN_A"] = "1.01"
    if change == "duplicate_target":
        data["targets"].append(data["targets"][0])
    if change == "naive_time":
        data["sessions"][0]["decision_at"] = DATES[0] + "T16:00:00"
    if change == "decision_after_next_open":
        data["sessions"][0]["decision_at"] = DATES[1] + "T16:00:00+07:00"
    if change == "invalid_ohlc":
        data["bars"][0]["low"] = "12"
    if change == "unknown_adjustment":
        data["adjustment_status"] = "unknown"
    if change == "research_kind":
        data["kind"] = "strict_historical"
    if change == "boolean_volume":
        data["bars"][0]["volume"] = True
    with pytest.raises(ValueError):
        Scenario.model_validate(data)


def test_mutated_nested_model_is_revalidated_and_bad_decimal_inputs_rejected():
    data = scenario()
    data.targets[0].weights.clear()
    with pytest.raises(ValueError):
        simulate(data, config())
    for updates in [
        {"initial_cash": "NaN"},
        {"initial_cash": "0"},
        {"lot_size": True},
        {"buy_fee_bps": 1.5},
        {"share_settlement_sessions": -1},
    ]:
        with pytest.raises(ValueError):
            config(**updates)


def test_q0_and_q1_schedules_do_not_use_returns_or_fabricate_predictions():
    data = scenario(symbols=["SYN_A", "SYN_B", "SYN_C"], targets=[(0, ["1", "0", "0"])])
    q0 = schedule(data, "Q0")
    assert len(q0.targets) == 1 and set(q0.targets[0].weights.values()) == {"0.33333333"}
    q1 = schedule(data, "Q1", 2)
    assert [t.session for t in q1.targets] == DATES[::2]
    assert simulate(q1, config())["metrics"]["macro_f1"] is None
    changed = data.model_dump()
    changed["bars"][-1].update(open="100", close="90", high="101", low="89")
    assert schedule(Scenario.model_validate(changed), "Q1", 2).targets == q1.targets


@pytest.mark.parametrize(
    "policy,interval",
    [("Q2", None), ("Q1", None), ("Q1", 0), ("Q1", True), ("Q0", 2), ("manual", 2)],
)
def test_unimplemented_or_ambiguous_baseline_settings_are_rejected(policy, interval):
    with pytest.raises(ValueError):
        schedule(scenario(), policy, interval)


def reseal(folder):
    write_json(
        folder / "integrity.json",
        {"files": {p.name: file_sha(p) for p in folder.iterdir() if p.name != "integrity.json"}},
    )


def test_snapshot_preserves_raw_inputs_and_replays_without_network_or_models(tmp_path):
    raw = b" \n" + demo().model_dump_json().encode()
    raw_config = config().model_dump_json().encode() + b"\r\n"
    folder, result = run(tmp_path, raw, raw_config, baseline="Q1", rebalance_every=2)
    assert (folder / "original.json").read_bytes() == raw
    assert (folder / "config.json").read_bytes() == raw_config
    assert replay(tmp_path, folder) == result
    assert (folder / "positions.csv").read_text().startswith("session,symbol,quantity")
    assert result["research_result"] is result["historical_availability_validated"] is False
    assert not (tmp_path / "data").exists()


def test_all_cash_exports_have_headers_and_do_not_fabricate_trades_or_returns(tmp_path):
    data = scenario().model_dump()
    data["targets"] = []
    folder, result = run(tmp_path, json.dumps(data).encode(), config().model_dump_json().encode())
    assert result["orders"] == result["trades"] == []
    assert result["metrics"]["net_return"] == result["metrics"]["max_drawdown"] == "0"
    assert len((folder / "trades.csv").read_text().splitlines()) == 1
    assert replay(tmp_path, folder) == result


@pytest.mark.parametrize(
    "change",
    [
        "raw",
        "result_resealed",
        "csv_resealed",
        "scenario_resealed",
        "provenance_resealed",
        "missing_seal_entry",
    ],
)
def test_tampered_runs_cannot_replay_even_when_outer_checksums_are_resealed(tmp_path, change):
    folder, _ = run(
        tmp_path, demo().model_dump_json().encode(), config().model_dump_json().encode()
    )
    if change == "raw":
        (folder / "original.json").write_bytes(b"changed")
    if change == "result_resealed":
        data = json.loads((folder / "result.json").read_bytes())
        data["metrics"]["net_return"] = "999"
        write_json(folder / "result.json", data)
    if change == "csv_resealed":
        (folder / "trades.csv").write_bytes(b"forged\n")
    if change == "scenario_resealed":
        data = json.loads((folder / "scenario.json").read_bytes())
        data["targets"] = []
        write_json(folder / "scenario.json", data)
        manifest = json.loads((folder / "manifest.json").read_bytes())
        manifest["scenario_sha256"] = file_sha(folder / "scenario.json")
        write_json(folder / "manifest.json", manifest)
    if change == "provenance_resealed":
        manifest = json.loads((folder / "manifest.json").read_bytes())
        manifest["research_result"] = True
        write_json(folder / "manifest.json", manifest)
    if change != "raw":
        reseal(folder)
    if change == "missing_seal_entry":
        seal = json.loads((folder / "integrity.json").read_bytes())
        del seal["files"]["trades.csv"]
        write_json(folder / "integrity.json", seal)
    with pytest.raises(ValueError, match="differs|differ|Incomplete"):
        replay(tmp_path, folder)


def test_invalid_run_does_not_create_outputs_and_replay_refuses_external_directory(tmp_path):
    with pytest.raises(ValueError):
        run(tmp_path, b"{}", config().model_dump_json().encode())
    assert not (tmp_path / "outputs").exists()
    with pytest.raises(ValueError):
        replay(tmp_path, tmp_path)


def test_cli_demo_and_saved_replay_reject_overrides(tmp_path):
    config_path = tmp_path / "config.json"
    config_path.write_text(config().model_dump_json(), encoding="utf-8")
    cmd = [sys.executable, "-X", "utf8", "-m", "pit_haf.backtest.runner", "--root", str(tmp_path)]
    response = subprocess.run(
        [*cmd, "--demo", "--config", str(config_path), "--baseline", "Q0"],
        capture_output=True,
        check=True,
    )
    saved = json.loads(response.stdout)
    assert saved["research_result"] is False and Path(saved["path"]).is_dir()
    replayed = subprocess.run([*cmd, "--replay", saved["path"]], capture_output=True, check=True)
    assert json.loads(replayed.stdout) == saved
    rejected = subprocess.run(
        [*cmd, "--replay", saved["path"], "--baseline", "Q1"], capture_output=True
    )
    assert rejected.returncode == 2 and b"omit overrides" in rejected.stderr
