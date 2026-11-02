"""Run/replay synthetic execution diagnostics; never downloads or trades market data."""

import argparse
import csv
import io
import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from pit_haf.backtest import baselines, contracts, engine
from pit_haf.data.hub import file_sha
from pit_haf.llm.ollama import write_json

SOURCES = {"contracts.py": contracts, "engine.py": engine, "baselines.py": baselines}
CSV_FIELDS = {
    "orders.csv": "order_id symbol side signal_session signal_at target_weight sizing_nav sizing_close requested_quantity execution_session execution_at open_reference fill_price filled_quantity fee status reasons".split(),
    "trades.csv": "order_id session at symbol side quantity open_reference price notional fee slippage_cost cash_effect_including_unsettled".split(),
    "cash_ledger.csv": "event session order_id amount cash_after".split(),
    "equity_curve.csv": "session at available_cash unsettled_sale_cash equity cumulative_fees".split(),
    "positions.csv": "session symbol quantity settled_quantity close market_value".split(),
}


def demo():
    dates = ["2024-01-02", "2024-01-03", "2024-01-05", "2024-01-08", "2024-01-09", "2024-01-11"]
    sessions = [
        {
            "date": d,
            "open_at": d + "T09:00:00+07:00",
            "close_at": d + "T15:00:00+07:00",
            "decision_at": d + "T16:00:00+07:00",
        }
        for d in dates
    ]
    bars = []
    for i, d in enumerate(dates):
        for symbol, opens, closes in [
            ("SYN_A", [100, 103, 98, 101, 107, 104], [102, 99, 100, 106, 105, 108]),
            ("SYN_B", [50, 49, 52, 53, 51, 54], [49, 51, 53, 50, 54, 55]),
        ]:
            o, c = opens[i], closes[i]
            bars.append(
                {
                    "session": d,
                    "symbol": symbol,
                    "open": str(o),
                    "close": str(c),
                    "high": str(max(o, c) + 1),
                    "low": str(min(o, c) - 1),
                    "volume": 100000,
                }
            )
    return contracts.Scenario.model_validate(
        {
            "kind": "synthetic_execution_diagnostic",
            "adjustment_status": "synthetic_no_corporate_actions",
            "calendar_basis": "explicit_synthetic_sessions",
            "currency": "scenario_units",
            "symbols": ["SYN_A", "SYN_B"],
            "sessions": sessions,
            "bars": bars,
            "targets": [
                {"session": dates[0], "weights": {"SYN_A": "1", "SYN_B": "0"}},
                {"session": dates[2], "weights": {"SYN_A": "0", "SYN_B": "1"}},
                {"session": dates[4], "weights": {"SYN_A": "0", "SYN_B": "0"}},
            ],
        }
    )


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
    }


def output_base(root):
    base = root / "outputs/backtest-synthetic"
    if base.parent.is_symlink() or base.is_symlink() or base.resolve() != base:
        raise ValueError("Synthetic runs must stay in project outputs")
    return base


def run(root, original_bytes, config_bytes, *, baseline="manual", rebalance_every=None):
    root = root.resolve()
    if max(len(original_bytes), len(config_bytes)) > 32 * 1024 * 1024:
        raise ValueError("Synthetic input exceeds 32 MiB budget")
    original = contracts.Scenario.model_validate_json(original_bytes)
    config = contracts.ExecutionConfig.model_validate_json(config_bytes)
    scenario = baselines.schedule(original, baseline, rebalance_every)
    result = engine.simulate(scenario, config)
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
    (folder / "runner.py").write_bytes(Path(__file__).read_bytes())
    write_json(
        folder / "manifest.json",
        {
            "kind": original.kind,
            "protocol": config.protocol,
            "research_result": False,
            "baseline": baseline,
            "rebalance_every_sessions": rebalance_every,
            "original_sha256": file_sha(folder / "original.json"),
            "config_sha256": file_sha(folder / "config.json"),
            "scenario_sha256": file_sha(folder / "scenario.json"),
            "new_llm_calls": 0,
            "new_data_downloads": 0,
            "independent_gold": False,
            "historical_availability_validated": False,
            "code_hashes": {name: file_sha(folder / name) for name in [*SOURCES, "runner.py"]},
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
    seal = json.loads((folder / "integrity.json").read_bytes())
    required = {
        "original.json",
        "config.json",
        "scenario.json",
        "result.json",
        "manifest.json",
        *SOURCES,
        "runner.py",
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
    manifest = json.loads((folder / "manifest.json").read_bytes())
    original = contracts.Scenario.model_validate_json((folder / "original.json").read_bytes())
    config = contracts.ExecutionConfig.model_validate_json((folder / "config.json").read_bytes())
    expected = baselines.schedule(
        original, manifest["baseline"], manifest["rebalance_every_sessions"]
    )
    saved = contracts.Scenario.model_validate_json((folder / "scenario.json").read_bytes())
    if (
        expected != saved
        or manifest["original_sha256"] != file_sha(folder / "original.json")
        or manifest["config_sha256"] != file_sha(folder / "config.json")
        or manifest["scenario_sha256"] != file_sha(folder / "scenario.json")
    ):
        raise ValueError("Synthetic run inputs or schedule differ")
    if (
        manifest["kind"] != original.kind
        or manifest["protocol"] != config.protocol
        or manifest["research_result"] is not False
        or manifest["historical_availability_validated"] is not False
        or manifest["independent_gold"] is not False
        or manifest["new_llm_calls"] != 0
        or manifest["new_data_downloads"] != 0
        or manifest["code_hashes"]
        != {name: file_sha(folder / name) for name in [*SOURCES, "runner.py"]}
    ):
        raise ValueError("Synthetic run provenance differs")
    result = engine.simulate(saved, config)
    if result != json.loads((folder / "result.json").read_bytes()):
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
        config = (args.config or args.root / "configs/synthetic_execution_v0_1.json").read_bytes()
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
