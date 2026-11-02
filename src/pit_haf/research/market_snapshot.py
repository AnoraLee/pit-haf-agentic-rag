"""Bounded public KBS price capture/replay, never a historical backtest or an agent data gateway."""

import argparse
import csv
import io
import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from pit_haf.backtest.contracts import VN_OFFSET, instant
from pit_haf.data import market_prices
from pit_haf.data.hub import file_sha
from pit_haf.data.market_prices import CapturePlan, audit, decode, source_url
from pit_haf.data.pilot import approved_url, fetch_public
from pit_haf.llm.ollama import write_json


def base_for(root):
    base = root / "outputs/market-snapshots"
    if base.parent.is_symlink() or base.is_symlink() or base.resolve() != base:
        raise ValueError("Market snapshots must stay in project outputs")
    return base


def csv_bytes(normalized):
    output = io.StringIO(newline="")
    fields = [
        "symbol",
        "asset_type",
        "price_unit",
        "session_date",
        "source_time",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "available_at",
    ]
    writer = csv.DictWriter(output, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for entry in normalized:
        n = entry.get("normalized")
        if n:
            for bar in n["bars"]:
                writer.writerow(
                    {
                        "symbol": n["symbol"],
                        "asset_type": n["asset_type"],
                        "price_unit": n["price_unit"],
                        **bar,
                    }
                )
    return output.getvalue().encode()


def derive(folder, plan):
    entries = []
    for instrument in plan.instruments:
        directory = folder / instrument.symbol
        outcome = json.loads((directory / "outcome.json").read_bytes())
        if set(outcome) != {"transport", "error"}:
            raise ValueError("Unexpected market transport outcome fields")
        normalized, error = None, outcome.get("error")
        if outcome["transport"] == "captured":
            if error is not None:
                raise ValueError("Captured market transport cannot contain an error")
            metadata = json.loads((directory / "http.json").read_bytes())
            validate_http(metadata, source_url(plan, instrument))
            try:
                normalized = decode((directory / "response.raw").read_bytes(), plan, instrument)
            except (ValueError, TypeError, KeyError) as exc:
                error = str(exc)
        elif outcome["transport"] != "failed" or not isinstance(error, str) or not error:
            raise ValueError("Invalid market transport outcome")
        entries.append({"symbol": instrument.symbol, "normalized": normalized, "error": error})
    return entries, audit(plan, entries)


def validate_http(metadata, url):
    if (
        not isinstance(metadata, dict)
        or not {"source_url", "final_url", "http_status", "retrieved_at"} <= set(metadata)
        or any(
            not isinstance(metadata[k], str) for k in ("source_url", "final_url", "retrieved_at")
        )
    ):
        raise ValueError("Incomplete market HTTP provenance")
    if (
        metadata["source_url"] != url
        or type(metadata["http_status"]) is not int
        or metadata["http_status"] != 200
    ):
        raise ValueError("Market HTTP metadata does not match the requested source")
    approved_url(metadata["final_url"], {market_prices.HOST})
    instant(metadata["retrieved_at"])
    headers = metadata.get("headers", {})
    if not isinstance(headers, dict) or any(
        not isinstance(k, str) or not isinstance(v, str) for k, v in headers.items()
    ):
        raise ValueError("Market HTTP headers must be an object")


def capture(root, config_bytes, *, fetcher=fetch_public):
    root = root.resolve()
    plan = CapturePlan.model_validate_json(config_bytes)
    if plan.end >= datetime.now(VN_OFFSET).date().isoformat():
        raise ValueError("Capture requires a completed past end date")
    folder = base_for(root) / (datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ-") + uuid4().hex[:8])
    folder.mkdir(parents=True)
    (folder / "config.json").write_bytes(config_bytes)
    (folder / "market_prices.py").write_bytes(Path(market_prices.__file__).read_bytes())
    (folder / "market_snapshot.py").write_bytes(Path(__file__).read_bytes())
    for instrument in plan.instruments:
        directory = folder / instrument.symbol
        directory.mkdir()
        url = source_url(plan, instrument)
        try:
            payload, metadata = fetcher(
                url, {market_prices.HOST}, timeout=30, max_bytes=8 * 1024 * 1024
            )
            validate_http(metadata, url)
        except (OSError, ValueError) as exc:
            write_json(directory / "outcome.json", {"transport": "failed", "error": str(exc)})
        else:
            (directory / "response.raw").write_bytes(payload)
            # Save useful HTTP provenance, never cookies/authorization or arbitrary headers.
            kept_headers = {
                k: v
                for k, v in metadata.get("headers", {}).items()
                if k.lower() in {"content-type", "date", "etag", "last-modified", "content-length"}
            }
            write_json(
                directory / "http.json",
                {k: metadata[k] for k in ("source_url", "final_url", "http_status", "retrieved_at")}
                | {"headers": kept_headers},
            )
            write_json(directory / "outcome.json", {"transport": "captured", "error": None})
    entries, report = derive(folder, plan)
    write_json(folder / "normalized.json", entries)
    write_json(folder / "quality.json", report)
    (folder / "prices.csv").write_bytes(csv_bytes(entries))
    write_json(
        folder / "manifest.json",
        {
            "protocol": market_prices.PROTOCOL,
            "kind": report["kind"],
            "research_result": False,
            "config_sha256": file_sha(folder / "config.json"),
            "transport": "direct_public_KBS_GET; no_vnstock_import_or_API_key",
            "raw_semantics": "HTTP_response_bytes; prices_not_independently_verified; retrieved_now_not_available_then",
            "requests": [
                {"symbol": i.symbol, "url": source_url(plan, i)} for i in plan.instruments
            ],
            "code_hashes": {
                n: file_sha(folder / n) for n in ("market_prices.py", "market_snapshot.py")
            },
        },
    )
    write_json(
        folder / "integrity.json",
        {
            "files": {
                p.relative_to(folder).as_posix(): file_sha(p)
                for p in folder.rglob("*")
                if p.is_file()
            }
        },
    )
    return folder, report


def replay(root, folder):
    root, folder = root.resolve(), Path(folder).absolute()
    if (
        folder.is_symlink()
        or folder.parent != base_for(root)
        or folder.resolve().parent != base_for(root)
    ):
        raise ValueError("Replay must select a market snapshot inside project outputs")
    seal = json.loads((folder / "integrity.json").read_bytes())
    paths = {
        p.relative_to(folder).as_posix(): p
        for p in folder.rglob("*")
        if p.is_file() and p.name != "integrity.json"
    }
    if set(paths) != set(seal["files"]):
        raise ValueError("Market snapshot file set differs")
    for name, path in paths.items():
        if (
            path.is_symlink()
            or not path.resolve().is_relative_to(folder)
            or file_sha(path) != seal["files"][name]
        ):
            raise ValueError("Market snapshot checksum differs")
    plan = CapturePlan.model_validate_json((folder / "config.json").read_bytes())
    expected = {
        "config.json",
        "market_prices.py",
        "market_snapshot.py",
        "normalized.json",
        "quality.json",
        "prices.csv",
        "manifest.json",
    }
    for instrument in plan.instruments:
        expected.add(instrument.symbol + "/outcome.json")
        outcome = json.loads((folder / instrument.symbol / "outcome.json").read_bytes())
        if outcome["transport"] == "captured":
            expected.update({instrument.symbol + "/response.raw", instrument.symbol + "/http.json"})
    if set(paths) != expected or any(p.is_symlink() for p in folder.rglob("*")):
        raise ValueError("Market snapshot required file set differs")
    manifest = json.loads((folder / "manifest.json").read_bytes())
    if (
        manifest["protocol"] != market_prices.PROTOCOL
        or manifest["kind"] != "real_market_snapshot_quality_diagnostic"
        or manifest["research_result"] is not False
        or manifest["config_sha256"] != file_sha(folder / "config.json")
        or manifest["requests"]
        != [{"symbol": i.symbol, "url": source_url(plan, i)} for i in plan.instruments]
        or manifest["code_hashes"]
        != {n: file_sha(folder / n) for n in ("market_prices.py", "market_snapshot.py")}
    ):
        raise ValueError("Market snapshot provenance differs")
    entries, report = derive(folder, plan)
    if (
        entries != json.loads((folder / "normalized.json").read_bytes())
        or report != json.loads((folder / "quality.json").read_bytes())
        or csv_bytes(entries) != (folder / "prices.csv").read_bytes()
    ):
        raise ValueError("Recomputed market prices or quality report differ")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--capture", action="store_true")
    group.add_argument("--replay", type=Path)
    parser.add_argument("--config", type=Path)
    args = parser.parse_args()
    if args.replay:
        if args.config:
            parser.error("Replay uses its saved config; omit overrides")
        folder, report = args.replay, replay(args.root, args.replay)
    else:
        config = args.config or args.root / "configs/market_snapshot_v0_1.json"
        folder, report = capture(args.root, config.read_bytes())
    print(
        json.dumps(
            {
                "path": str(folder),
                "successful_instruments": report["successful_instruments"],
                "failed_instruments": report["failed_instruments"],
                "eligible_for_execution": False,
                "research_result": False,
                "assets": report["assets"],
            }
        )
    )
    return 2 if report["failed_instruments"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
