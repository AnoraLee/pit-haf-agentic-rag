"""Offline source-bound calendar/date reconciliation; never enables market execution."""

import argparse
import csv
import io
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from pit_haf.backtest.contracts import instant
from pit_haf.data import session_calendar
from pit_haf.data.hub import file_sha
from pit_haf.data.market_prices import CapturePlan, unique_object
from pit_haf.data.session_calendar import Profile, build_calendar, reconcile, validate_sources
from pit_haf.llm.ollama import write_json
from pit_haf.research import market_snapshot

RUN = r"\d{8}T\d{6}Z-[a-f0-9]{8}"
FIELDS = {
    "calendar.csv": "date revision weekday candidate_settlement_day reason source_id available_at".split(),
    "settlement_dates.csv": "trade_date candidate_T2_date shares_available_at sale_cash_available_at".split(),
    "revision_changes.csv": "date prior_revision revision prior_open revised_open".split(),
}


def decode(raw):
    if len(raw) > 32 * 1024 * 1024:
        raise ValueError("Calendar JSON exceeds 32 MiB")

    def invalid(value):
        raise ValueError("Non-finite JSON calendar number")

    return json.loads(raw, object_pairs_hook=unique_object, parse_constant=invalid)


def output_base(root, name):
    base = root / "outputs" / name
    if base.is_symlink() or base.parent.is_symlink() or base.resolve() != base:
        raise ValueError("Calendar dependencies must stay in project outputs")
    return base


def dependency(root, kind, run_id):
    if not re.fullmatch(RUN, run_id):
        raise ValueError("Invalid calendar dependency run ID")
    folder = output_base(root, kind) / run_id
    if folder.is_symlink() or folder.resolve() != folder:
        raise ValueError("Calendar dependency cannot be redirected")
    return folder


def verify_flat(folder, required=None):
    seal_path = folder / "integrity.json"
    if seal_path.is_symlink() or seal_path.resolve().parent != folder:
        raise ValueError("Calendar seal path differs")
    seal = decode((folder / "integrity.json").read_bytes())
    names = set(seal["files"])
    if (required is not None and names != required) or {
        p.name for p in folder.iterdir()
    } != names | {"integrity.json"}:
        raise ValueError("Calendar artifact file set differs")
    for name, digest in seal["files"].items():
        path = folder / name
        if (
            Path(name).name != name
            or path.is_symlink()
            or not path.is_file()
            or path.resolve().parent != folder
            or file_sha(path) != digest
        ):
            raise ValueError("Calendar artifact checksum or file path differs")


def derive(root, profile, sources_run, market_run):
    source = dependency(root, "calendar-sources", sources_run)
    verify_flat(source)
    source_plan = decode((source / "source_plan.json").read_bytes())
    manifest = decode((source / "manifest.json").read_bytes())
    expected_sources = [{"id": s.id, "url": s.url} for s in profile.sources]
    if (
        source_plan != {"protocol": "calendar_source_capture_v0.1", "sources": expected_sources}
        or manifest["protocol"] != source_plan["protocol"]
        or manifest["research_result"] is not False
    ):
        raise ValueError("Calendar source plan differs")
    required = {"source_plan.json", "manifest.json", "capture-calendar-sources.ps1"}
    payloads = {}
    if len(manifest["sources"]) != len(profile.sources):
        raise ValueError("Incomplete source transport records")
    for spec, saved in zip(profile.sources, manifest["sources"]):
        required.update({spec.id + ".raw", spec.id + ".json"})
        metadata = decode((source / (spec.id + ".json")).read_bytes())
        raw = (source / (spec.id + ".raw")).read_bytes()
        if (
            metadata != saved
            or metadata["id"] != spec.id
            or metadata["url"] != spec.url
            or metadata["status"] != "captured"
            or metadata["http_status"] != 200
            or metadata["certificate_verification_disabled"] is not False
            or metadata["authentication_used"] is not False
            or metadata["automatic_retries"] != 0
            or metadata["sha256"] != spec.raw_sha256
            or metadata["bytes"] != len(raw)
        ):
            raise ValueError("Calendar source transport metadata differs")
        instant(metadata["captured_at"])
        payloads[spec.id] = raw
    verify_flat(source, required)
    sources = validate_sources(profile, payloads)
    market = dependency(root, "market-snapshots", market_run)
    market_snapshot.replay(root, market)
    plan = CapturePlan.model_validate(decode((market / "config.json").read_bytes()))
    if (plan.start, plan.end) != (profile.audit_start, profile.audit_end):
        raise ValueError("Calendar audit must use the complete pinned market request window")
    normalized = decode((market / "normalized.json").read_bytes())
    types = {i.symbol: i.asset_type for i in plan.instruments}
    observed, unavailable = {}, []
    for entry in normalized:
        if types[entry["symbol"]] != "equity" or entry["normalized"] is None:
            unavailable.append(
                {
                    "symbol": entry["symbol"],
                    "asset_type": types[entry["symbol"]],
                    "reason": entry["error"] or "outside_cash_equity_scope",
                }
            )
        else:
            observed[entry["symbol"]] = [b["session_date"] for b in entry["normalized"]["bars"]]
    calendar, changes = build_calendar(profile)
    report = reconcile(profile, calendar, observed)
    if any(a["asset_type"] == "equity" for a in unavailable):
        report["date_sets_match"] = False
    report["unassessed_instruments"] = unavailable
    report["revision_changes"] = changes
    binding = {
        "sources_run": sources_run,
        "sources_seal_sha256": file_sha(source / "integrity.json"),
        "market_run": market_run,
        "market_seal_sha256": file_sha(market / "integrity.json"),
    }
    return {
        "calendar.json": calendar,
        "sources.json": sources,
        "observed.json": observed,
        "report.json": report,
    }, binding


def csv_bytes(rows, fields):
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue().encode()


def exports(artifacts):
    return {
        "calendar.csv": artifacts["calendar.json"],
        "settlement_dates.csv": artifacts["report.json"]["candidate_T2_dates"],
        "revision_changes.csv": artifacts["report.json"]["revision_changes"],
    }


def run(root, profile_bytes, sources_run, market_run):
    root = root.resolve()
    profile = Profile.model_validate(decode(profile_bytes))
    artifacts, binding = derive(root, profile, sources_run, market_run)
    folder = output_base(root, "calendar-audits") / (
        datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ-") + uuid4().hex[:8]
    )
    folder.mkdir(parents=True)
    (folder / "profile.json").write_bytes(profile_bytes)
    (folder / "session_calendar.py").write_bytes(Path(session_calendar.__file__).read_bytes())
    (folder / "calendar_audit.py").write_bytes(Path(__file__).read_bytes())
    for name, value in artifacts.items():
        write_json(folder / name, value)
    for name, rows in exports(artifacts).items():
        (folder / name).write_bytes(csv_bytes(rows, FIELDS[name]))
    write_json(
        folder / "manifest.json",
        {
            "protocol": session_calendar.PROTOCOL,
            "kind": "retrospective_settlement_calendar_diagnostic",
            "research_result": False,
            "eligible_for_execution": False,
            "venue_calendar_verified": False,
            "historical_availability_validated": False,
            "independent_gold": False,
            "profile_sha256": file_sha(folder / "profile.json"),
            "binding": binding,
            "new_market_downloads": 0,
            "new_llm_calls": 0,
            "code_hashes": {
                n: file_sha(folder / n) for n in ["session_calendar.py", "calendar_audit.py"]
            },
        },
    )
    write_json(
        folder / "integrity.json", {"files": {p.name: file_sha(p) for p in folder.iterdir()}}
    )
    return folder, artifacts["report.json"]


def replay(root, folder):
    root, folder = root.resolve(), Path(folder).absolute()
    if (
        folder.is_symlink()
        or folder.parent != output_base(root, "calendar-audits")
        or folder.resolve().parent != folder.parent
    ):
        raise ValueError("Replay must select a calendar audit inside project outputs")
    required = {
        "profile.json",
        "session_calendar.py",
        "calendar_audit.py",
        "manifest.json",
        "calendar.json",
        "sources.json",
        "observed.json",
        "report.json",
        *FIELDS,
    }
    verify_flat(folder, required)
    manifest = decode((folder / "manifest.json").read_bytes())
    profile = Profile.model_validate(decode((folder / "profile.json").read_bytes()))
    artifacts, binding = derive(
        root, profile, manifest["binding"]["sources_run"], manifest["binding"]["market_run"]
    )
    if (
        binding != manifest["binding"]
        or manifest["protocol"] != session_calendar.PROTOCOL
        or manifest["kind"] != "retrospective_settlement_calendar_diagnostic"
        or any(
            manifest[k] is not False
            for k in [
                "research_result",
                "eligible_for_execution",
                "venue_calendar_verified",
                "historical_availability_validated",
                "independent_gold",
            ]
        )
        or manifest["profile_sha256"] != file_sha(folder / "profile.json")
        or manifest["new_market_downloads"] != 0
        or manifest["new_llm_calls"] != 0
        or manifest["code_hashes"]
        != {n: file_sha(folder / n) for n in ["session_calendar.py", "calendar_audit.py"]}
    ):
        raise ValueError("Calendar audit provenance differs")
    if any(value != decode((folder / name).read_bytes()) for name, value in artifacts.items()):
        raise ValueError("Recomputed calendar JSON differs")
    if any(
        csv_bytes(rows, FIELDS[name]) != (folder / name).read_bytes()
        for name, rows in exports(artifacts).items()
    ):
        raise ValueError("Recomputed calendar CSV differs")
    return artifacts["report.json"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--build", action="store_true")
    group.add_argument("--replay", type=Path)
    parser.add_argument("--config", type=Path)
    parser.add_argument("--sources-run")
    parser.add_argument("--market-run")
    args = parser.parse_args()
    if args.replay:
        if args.config or args.sources_run or args.market_run:
            parser.error("Replay uses saved dependencies; omit overrides")
        folder, report = args.replay, replay(args.root, args.replay)
    else:
        if not args.sources_run or not args.market_run:
            parser.error("Build requires --sources-run and --market-run")
        folder, report = run(
            args.root,
            (args.config or args.root / "configs/settlement_calendar_v0_1.json").read_bytes(),
            args.sources_run,
            args.market_run,
        )
    print(
        json.dumps(
            {
                "path": str(folder),
                "date_sets_match": report["date_sets_match"],
                "candidate_sessions": report["candidate_sessions"],
                "eligible_for_execution": False,
                "research_result": False,
            }
        )
    )
    return 0 if report["date_sets_match"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
