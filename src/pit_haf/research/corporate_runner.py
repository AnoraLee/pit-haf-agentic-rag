"""Offline corporate-action source audit and synthetic entitlement accounting demo."""

import argparse
import csv
import io
import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from pit_haf.backtest import corporate_ledger
from pit_haf.backtest.contracts import instant
from pit_haf.data import corporate_actions
from pit_haf.data.corporate_actions import Book
from pit_haf.data.hub import file_sha
from pit_haf.data.market_prices import CapturePlan
from pit_haf.llm.ollama import write_json
from pit_haf.research import calendar_audit, market_snapshot
from pit_haf.research.calendar_audit import decode, dependency, output_base, verify_flat

FIELDS = {
    "events.csv": "id symbol record_date ex_date cash_per_share cash_basis cash_payment_date ratio_old ratio_new stock_tradable_date calendar_days_record_to_stock_trading record_date_in_price_snapshot stock_trading_date_in_price_snapshot snapshot_adjustment_status availability_at entitlement_quantity blocking_reasons record_date_status".split(),
    "receipts.csv": "event_id symbol kind amount quantity available_at observed_at".split(),
    "checkpoints.csv": "at spendable_dividend_cash tradable_shares net_cash_receivable pending_stock_value total_pending_value total_value_with_base_position".split(),
}


def source_payloads(root, book, sources_run):
    folder = dependency(root, "calendar-sources", sources_run)
    verify_flat(folder)
    plan = decode((folder / "source_plan.json").read_bytes())
    manifest = decode((folder / "manifest.json").read_bytes())
    expected = [{"id": s.id, "url": s.url} for s in book.sources]
    if (
        plan != {"protocol": "calendar_source_capture_v0.1", "sources": expected}
        or manifest["protocol"] != plan["protocol"]
        or manifest["research_result"] is not False
        or len(manifest["sources"]) != len(expected)
    ):
        raise ValueError("Corporate source plan differs")
    required = {"manifest.json", "source_plan.json", "capture-calendar-sources.ps1"}
    payloads = {}
    for source, saved in zip(book.sources, manifest["sources"]):
        required.update({source.id + ".raw", source.id + ".json"})
        meta = decode((folder / (source.id + ".json")).read_bytes())
        raw = (folder / (source.id + ".raw")).read_bytes()
        if (
            meta != saved
            or meta["id"] != source.id
            or meta["url"] != source.url
            or meta["status"] != "captured"
            or meta["http_status"] != 200
            or meta["certificate_verification_disabled"] is not False
            or meta["authentication_used"] is not False
            or meta["automatic_retries"] != 0
            or meta["sha256"] != source.raw_sha256
            or meta["bytes"] != len(raw)
        ):
            raise ValueError("Corporate source transport differs")
        payloads[source.id] = raw
        instant(meta["captured_at"])
    verify_flat(folder, required)
    return payloads, file_sha(folder / "integrity.json")


def derive(root, mode, book_bytes, sources_run, market_run):
    if mode == "demo":
        if book_bytes is not None or sources_run is not None or market_run is not None:
            raise ValueError("Synthetic demo does not consume market sources or a real event book")
        result, binding = corporate_ledger.demo(), None
    elif mode == "audit":
        if book_bytes is None or not sources_run or not market_run:
            raise ValueError("Source audit requires book, source and market dependencies")
        book = Book.model_validate(decode(book_bytes))
        raw, source_seal = source_payloads(root, book, sources_run)
        market = dependency(root, "market-snapshots", market_run)
        market_snapshot.replay(root, market)
        plan = CapturePlan.model_validate(decode((market / "config.json").read_bytes()))
        if (plan.start, plan.end) != (book.audit_start, book.audit_end):
            raise ValueError("Corporate book and market window differ")
        pdfs = {}
        pdf_binding = []
        for item in book.disagreements:
            pdf_path = (
                root / "data/cache/evidence/blobs" / item.content_hash[:2] / item.content_hash
            )
            if (
                pdf_path.is_symlink()
                or pdf_path.resolve() != pdf_path
                or pdf_path.stat().st_size > 32 * 1024 * 1024
            ):
                raise ValueError("Corporate PDF dependency path or budget differs")
            pdfs[item.content_hash] = pdf_path.read_bytes()
            pdf_binding.append(
                {
                    "path": pdf_path.relative_to(root).as_posix(),
                    "sha256": item.content_hash,
                    "page": item.pdf_page,
                }
            )
        result = corporate_actions.audit(
            book, raw, decode((market / "normalized.json").read_bytes()), external_pdfs=pdfs
        )
        binding = {
            "sources_run": sources_run,
            "sources_seal_sha256": source_seal,
            "market_run": market_run,
            "market_seal_sha256": file_sha(market / "integrity.json"),
            "external_pdf_inputs": pdf_binding,
        }
    else:
        raise ValueError("Unknown corporate run mode")
    return result | {
        "protocol": corporate_actions.PROTOCOL,
        "eligible_for_execution": False,
        "historical_availability_validated": False,
    }, binding


def exports(result):
    return {
        "events.csv": result.get("events", []),
        "receipts.csv": result.get("ledger", {}).get("receipts", []),
        "checkpoints.csv": result.get("checkpoints", []),
    }


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
    return output.getvalue().encode()


def run(root, *, mode, book_bytes=None, sources_run=None, market_run=None):
    root = root.resolve()
    result, binding = derive(root, mode, book_bytes, sources_run, market_run)
    folder = output_base(root, "corporate-actions") / (
        datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ-") + uuid4().hex[:8]
    )
    folder.mkdir(parents=True)
    (folder / "book.json").write_bytes(book_bytes if book_bytes is not None else b"null\n")
    write_json(folder / "result.json", result)
    for name, rows in exports(result).items():
        (folder / name).write_bytes(csv_bytes(rows, FIELDS[name]))
    for name, module in {
        "corporate_ledger.py": corporate_ledger,
        "corporate_actions.py": corporate_actions,
        "calendar_audit.py": calendar_audit,
    }.items():
        (folder / name).write_bytes(Path(module.__file__).read_bytes())
    (folder / "corporate_runner.py").write_bytes(Path(__file__).read_bytes())
    write_json(
        folder / "manifest.json",
        {
            "protocol": corporate_actions.PROTOCOL,
            "mode": mode,
            "kind": result["kind"],
            "research_result": False,
            "eligible_for_execution": False,
            "independent_gold": False,
            "historical_availability_validated": False,
            "book_sha256": file_sha(folder / "book.json"),
            "binding": binding,
            "new_market_downloads": 0,
            "new_llm_calls": 0,
            "code_hashes": {
                name: file_sha(folder / name)
                for name in [
                    "corporate_ledger.py",
                    "corporate_actions.py",
                    "calendar_audit.py",
                    "corporate_runner.py",
                ]
            },
        },
    )
    write_json(
        folder / "integrity.json", {"files": {p.name: file_sha(p) for p in folder.iterdir()}}
    )
    return folder, result


def replay(root, folder):
    root, folder = root.resolve(), Path(folder).absolute()
    if (
        folder.is_symlink()
        or folder.parent != output_base(root, "corporate-actions")
        or folder.resolve().parent != folder.parent
    ):
        raise ValueError("Replay requires a corporate run inside project outputs")
    code = [
        "corporate_ledger.py",
        "corporate_actions.py",
        "calendar_audit.py",
        "corporate_runner.py",
    ]
    verify_flat(folder, {"book.json", "result.json", "manifest.json", *FIELDS, *code})
    manifest = decode((folder / "manifest.json").read_bytes())
    raw = (folder / "book.json").read_bytes()
    if manifest["mode"] == "demo" and (raw != b"null\n" or manifest["binding"] is not None):
        raise ValueError("Synthetic corporate provenance differs")
    binding = manifest["binding"] or {}
    result, calculated = derive(
        root,
        manifest["mode"],
        raw if manifest["mode"] == "audit" else None,
        binding.get("sources_run"),
        binding.get("market_run"),
    )
    if (
        manifest["protocol"] != corporate_actions.PROTOCOL
        or manifest["kind"] != result["kind"]
        or any(
            manifest[k] is not False
            for k in [
                "research_result",
                "eligible_for_execution",
                "independent_gold",
                "historical_availability_validated",
            ]
        )
        or manifest["book_sha256"] != file_sha(folder / "book.json")
        or calculated != manifest["binding"]
        or manifest["code_hashes"] != {name: file_sha(folder / name) for name in code}
        or manifest["new_market_downloads"] != 0
        or manifest["new_llm_calls"] != 0
    ):
        raise ValueError("Corporate run provenance differs")
    if result != decode((folder / "result.json").read_bytes()):
        raise ValueError("Recomputed corporate result differs")
    for name, rows in exports(result).items():
        if csv_bytes(rows, FIELDS[name]) != (folder / name).read_bytes():
            raise ValueError("Recomputed corporate CSV differs")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--demo", action="store_true")
    group.add_argument("--audit", action="store_true")
    group.add_argument("--replay", type=Path)
    parser.add_argument("--book", type=Path)
    parser.add_argument("--sources-run")
    parser.add_argument("--market-run")
    args = parser.parse_args()
    if args.replay:
        if args.book or args.sources_run or args.market_run:
            parser.error("Replay uses saved dependencies; omit overrides")
        folder, result = args.replay, replay(args.root, args.replay)
    else:
        if args.demo and (args.book or args.sources_run or args.market_run):
            parser.error("Demo does not consume a real source book or market data")
        if args.audit and (not args.sources_run or not args.market_run):
            parser.error("Audit requires --sources-run and --market-run")
        folder, result = run(
            args.root,
            mode="demo" if args.demo else "audit",
            book_bytes=(args.book or args.root / "configs/corporate_actions_v0_1.json").read_bytes()
            if args.audit
            else None,
            sources_run=args.sources_run,
            market_run=args.market_run,
        )
    print(
        json.dumps(
            {
                "path": str(folder),
                "kind": result["kind"],
                "research_result": False,
                "eligible_for_execution": False,
                "observed_events": len(result.get("events", [])),
                "checkpoints": len(result.get("checkpoints", [])),
            }
        )
    )


if __name__ == "__main__":
    main()
