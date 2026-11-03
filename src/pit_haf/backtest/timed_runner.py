"""Run/replay synthetic timestamp settlement diagnostics, entirely offline."""

import argparse
import csv
import io
import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from pit_haf.backtest import baselines, contracts, engine, runner, timed_contracts, timed_engine
from pit_haf.data.hub import file_sha
from pit_haf.llm.ollama import write_json

SOURCES = {
    "contracts.py": contracts,
    "engine.py": engine,
    "baselines.py": baselines,
    "runner.py": runner,
    "timed_contracts.py": timed_contracts,
    "timed_engine.py": timed_engine,
}
CSV_FIELDS = {
    "orders.csv": "order_id symbol side signal_session signal_at target_weight sizing_nav sizing_close requested_quantity execution_session execution_at open_reference fill_price filled_quantity fee status reasons".split(),
    "trades.csv": "order_id session at symbol side quantity open_reference price notional fee slippage_cost cash_effect_including_unsettled settlement_available_at".split(),
    "cash_ledger.csv": "event session at observed_at order_id amount cash_after".split(),
    "equity_curve.csv": "session at available_cash unsettled_sale_cash equity cumulative_fees".split(),
    "positions.csv": "session symbol quantity settled_quantity close market_value".split(),
    "settlement_schedule.csv": "trade_session trade_at share_settlement_date shares_available_at cash_settlement_date sale_cash_available_at".split(),
    "settlement_events.csv": "event at order_id symbol quantity amount observed_at".split(),
}


def demo():
    market = runner.demo()
    # Supplied fixture days, deliberately different from the sparse trading calendar.
    # These are not a certified exchange or settlement calendar.
    dates = [
        "2024-01-02",
        "2024-01-03",
        "2024-01-04",
        "2024-01-05",
        "2024-01-08",
        "2024-01-09",
        "2024-01-10",
        "2024-01-11",
        "2024-01-12",
        "2024-01-15",
    ]
    return timed_contracts.TimedScenario.model_validate(
        {
            "market": market.model_dump(),
            "settlement_basis": "explicit_synthetic_settlement_days",
            "settlement_days": [
                {"date": d, "shares_at": d + "T13:00:00+07:00", "cash_at": d + "T13:00:00+07:00"}
                for d in dates
            ],
        }
    )


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON object key")
        result[key] = value
    return result


def decode(raw):
    if len(raw) > 32 * 1024 * 1024:
        raise ValueError("Timed synthetic input exceeds 32 MiB budget")

    def invalid(value):
        raise ValueError("Non-finite JSON number")

    return json.loads(raw, object_pairs_hook=unique_object, parse_constant=invalid)


def csv_bytes(rows, fields):
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow(
            {
                k: json.dumps(v, ensure_ascii=False, sort_keys=True)
                if isinstance(v, (dict, list))
                else v
                for k, v in row.items()
            }
        )
    return output.getvalue().encode("utf-8")


def exports(result):
    positions = [
        {"session": row["session"], **p} for row in result["equity_curve"] for p in row["positions"]
    ]
    return {
        "orders.csv": result["orders"],
        "trades.csv": result["trades"],
        "cash_ledger.csv": result["cash_ledger"],
        "equity_curve.csv": [
            {k: v for k, v in row.items() if k != "positions"} for row in result["equity_curve"]
        ],
        "positions.csv": positions,
        "settlement_schedule.csv": result["settlement_schedule"],
        "settlement_events.csv": result["settlement_events"],
    }


def output_base(root):
    base = root / "outputs/backtest-timed-synthetic"
    if base.parent.is_symlink() or base.is_symlink() or base.resolve() != base:
        raise ValueError("Synthetic runs must stay in project outputs")
    return base


def run(root, original_bytes, config_bytes, *, baseline="manual", rebalance_every=None):
    root = root.resolve()
    if max(len(original_bytes), len(config_bytes)) > 32 * 1024 * 1024:
        raise ValueError("Synthetic input exceeds 32 MiB budget")
    original = timed_contracts.TimedScenario.model_validate(decode(original_bytes))
    config = timed_contracts.TimedConfig.model_validate(decode(config_bytes))
    market = baselines.schedule(original.market, baseline, rebalance_every)
    scenario = timed_contracts.TimedScenario.model_validate(
        original.model_dump() | {"market": market.model_dump()}
    )
    result = timed_engine.simulate(scenario, config)
    folder = output_base(root) / (datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ-") + uuid4().hex[:8])
    folder.mkdir(parents=True)
    (folder / "original.json").write_bytes(original_bytes)
    (folder / "config.json").write_bytes(config_bytes)
    write_json(folder / "scenario.json", scenario.model_dump())
    write_json(folder / "result.json", result)
    for filename, rows in exports(result).items():
        (folder / filename).write_bytes(csv_bytes(rows, CSV_FIELDS[filename]))
    for filename, module in SOURCES.items():
        (folder / filename).write_bytes(Path(module.__file__).read_bytes())
    (folder / "timed_runner.py").write_bytes(Path(__file__).read_bytes())
    write_json(
        folder / "manifest.json",
        {
            "kind": original.market.kind,
            "protocol": config.protocol,
            "research_result": False,
            "eligible_for_execution": False,
            "venue_calendar_verified": False,
            "baseline": baseline,
            "rebalance_every_sessions": rebalance_every,
            "original_sha256": file_sha(folder / "original.json"),
            "config_sha256": file_sha(folder / "config.json"),
            "scenario_sha256": file_sha(folder / "scenario.json"),
            "new_llm_calls": 0,
            "new_data_downloads": 0,
            "independent_gold": False,
            "historical_availability_validated": False,
            "code_hashes": {
                name: file_sha(folder / name) for name in [*SOURCES, "timed_runner.py"]
            },
        },
    )
    write_json(
        folder / "integrity.json",
        {"files": {p.name: file_sha(p) for p in folder.iterdir() if p.is_file()}},
    )
    return folder, result


def replay(root, folder):
    root, folder = root.resolve(), Path(folder).absolute()
    if (
        folder.is_symlink()
        or folder.resolve().parent != output_base(root)
        or folder.parent != output_base(root)
    ):
        raise ValueError("Replay must select a synthetic run inside project outputs")
    seal = decode((folder / "integrity.json").read_bytes())
    required = {
        "original.json",
        "config.json",
        "scenario.json",
        "result.json",
        "manifest.json",
        *SOURCES,
        "timed_runner.py",
        "settlement_schedule.csv",
        "settlement_events.csv",
        "orders.csv",
        "trades.csv",
        "cash_ledger.csv",
        "equity_curve.csv",
        "positions.csv",
    }
    if set(seal["files"]) != required or {p.name for p in folder.iterdir()} != required | {
        "integrity.json"
    }:
        raise ValueError("Incomplete or unexpected synthetic run files")
    for name, digest in seal["files"].items():
        path = folder / name
        if path.is_symlink() or path.resolve().parent != folder or file_sha(path) != digest:
            raise ValueError("Synthetic run checksum differs")
    manifest = decode((folder / "manifest.json").read_bytes())
    original = timed_contracts.TimedScenario.model_validate(
        decode((folder / "original.json").read_bytes())
    )
    config = timed_contracts.TimedConfig.model_validate(
        decode((folder / "config.json").read_bytes())
    )
    market = baselines.schedule(
        original.market, manifest["baseline"], manifest["rebalance_every_sessions"]
    )
    expected = timed_contracts.TimedScenario.model_validate(
        original.model_dump() | {"market": market.model_dump()}
    )
    saved = timed_contracts.TimedScenario.model_validate(
        decode((folder / "scenario.json").read_bytes())
    )
    if (
        expected != saved
        or manifest["original_sha256"] != file_sha(folder / "original.json")
        or manifest["config_sha256"] != file_sha(folder / "config.json")
        or manifest["scenario_sha256"] != file_sha(folder / "scenario.json")
    ):
        raise ValueError("Synthetic run inputs or schedule differ")
    if (
        manifest["kind"] != original.market.kind
        or manifest["protocol"] != config.protocol
        or manifest["research_result"] is not False
        or manifest["eligible_for_execution"] is not False
        or manifest["venue_calendar_verified"] is not False
        or manifest["historical_availability_validated"] is not False
        or manifest["independent_gold"] is not False
        or manifest["new_llm_calls"] != 0
        or manifest["new_data_downloads"] != 0
        or manifest["code_hashes"]
        != {name: file_sha(folder / name) for name in [*SOURCES, "timed_runner.py"]}
    ):
        raise ValueError("Synthetic run provenance differs")
    result = timed_engine.simulate(saved, config)
    if result != decode((folder / "result.json").read_bytes()):
        raise ValueError("Recomputed synthetic result differs")
    for name, rows in exports(result).items():
        if csv_bytes(rows, CSV_FIELDS[name]) != (folder / name).read_bytes():
            raise ValueError("Recomputed synthetic CSV differs")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--demo", action="store_true")
    group.add_argument("--scenario", type=Path)
    group.add_argument("--replay", type=Path)
    parser.add_argument("--config", type=Path)
    parser.add_argument("--baseline", choices=["manual", "Q0", "Q1"])
    parser.add_argument("--rebalance-every", type=int)
    args = parser.parse_args()
    if args.replay:
        if args.config or args.baseline or args.rebalance_every is not None:
            parser.error("Replay uses saved inputs; omit overrides")
        folder, result = args.replay, replay(args.root, args.replay)
    else:
        original = demo().model_dump_json().encode() if args.demo else args.scenario.read_bytes()
        config = (
            args.config or args.root / "configs/synthetic_timed_execution_v0_1.json"
        ).read_bytes()
        folder, result = run(
            args.root,
            original,
            config,
            baseline=args.baseline or "manual",
            rebalance_every=args.rebalance_every,
        )
    print(
        json.dumps(
            {
                "path": str(folder),
                "kind": result["kind"],
                "research_result": False,
                "metrics": result["metrics"],
            }
        )
    )


if __name__ == "__main__":
    main()
