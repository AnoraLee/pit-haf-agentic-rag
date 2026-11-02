"""Capture a read-only Vietcap chart query and compare VNINDEX fields with a pinned KBS snapshot."""

import argparse
import csv
import io
import json
import re
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from pit_haf.backtest.contracts import VN_OFFSET, instant
from pit_haf.data import index_prices
from pit_haf.data.hub import file_sha
from pit_haf.data.index_prices import IndexPlan, compare, kbs, request_body, vietcap
from pit_haf.data.market_prices import CapturePlan
from pit_haf.data.snapshots import canonical
from pit_haf.llm.ollama import write_json
from pit_haf.research import market_snapshot

RUN = r"\d{8}T\d{6}Z-[a-f0-9]{8}"


class NoChartRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise ValueError("No automatic redirect for read-only chart POST")


def fetch_chart(body):
    # This exact endpoint only queries chart data. No account/order API is called.
    request = urllib.request.Request(
        index_prices.VIETCAP_URL,
        data=body,
        method="POST",
        headers={
            "User-Agent": "PiTHAFResearchPilot/0.1 (local noncommercial research)",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.build_opener(NoChartRedirect()).open(request, timeout=30) as response:
            if response.status != 200 or response.headers.get("Content-Range"):
                raise ValueError("Expected a complete chart HTTP 200 response")
            length = response.headers.get("Content-Length")
            if length is not None and int(length) > 8 * 1024 * 1024:
                raise ValueError("Chart response exceeds 8 MiB")
            raw = response.read(8 * 1024 * 1024 + 1)
            if len(raw) > 8 * 1024 * 1024 or (length is not None and len(raw) != int(length)):
                raise ValueError("Chart response exceeds budget or content length differs")
            return raw, {
                "source_url": index_prices.VIETCAP_URL,
                "final_url": response.url,
                "http_status": response.status,
                "retrieved_at": datetime.now(UTC).isoformat(),
                "content_type": response.headers.get("Content-Type"),
            }
    except urllib.error.HTTPError as exc:
        raise ValueError(f"Chart source HTTP {exc.code}; no retry") from exc


def base_for(root):
    base = root / "outputs/index-crosschecks"
    if base.parent.is_symlink() or base.is_symlink() or base.resolve() != base:
        raise ValueError("Index crosschecks must stay in project outputs")
    return base


def kbs_source(root, run_id, plan):
    if not re.fullmatch(RUN, run_id):
        raise ValueError("Invalid KBS source run ID")
    folder = market_snapshot.base_for(root) / run_id
    market_snapshot.replay(root, folder)
    source_plan = CapturePlan.model_validate_json((folder / "config.json").read_bytes())
    if (source_plan.start, source_plan.end) != (plan.start, plan.end) or not any(
        i.symbol == "VNINDEX" and i.asset_type == "index" for i in source_plan.instruments
    ):
        raise ValueError("KBS index source must match the requested window and index identity")
    raw = folder / "VNINDEX/response.raw"
    data = kbs(raw.read_bytes(), plan)
    return data, {
        "run_id": run_id,
        "seal_sha256": file_sha(folder / "integrity.json"),
        "response_sha256": file_sha(raw),
    }


def validate_http(metadata):
    if not isinstance(metadata, dict) or not isinstance(metadata.get("retrieved_at"), str):
        raise ValueError("Incomplete chart HTTP provenance")
    if (
        metadata.get("source_url") != index_prices.VIETCAP_URL
        or metadata.get("final_url") != index_prices.VIETCAP_URL
        or type(metadata.get("http_status")) is not int
        or metadata["http_status"] != 200
    ):
        raise ValueError("Unexpected chart HTTP provenance")
    instant(metadata["retrieved_at"])


def derive(folder, plan, left):
    outcome = json.loads((folder / "outcome.json").read_bytes())
    if set(outcome) != {"transport", "error"}:
        raise ValueError("Unexpected chart transport outcome fields")
    right = None
    error = outcome["error"]
    if outcome["transport"] == "captured":
        if error is not None:
            raise ValueError("Captured chart cannot have a transport error")
        validate_http(json.loads((folder / "http.json").read_bytes()))
        try:
            right = vietcap((folder / "response.raw").read_bytes(), plan)
        except (ValueError, TypeError, KeyError) as exc:
            error = str(exc)
    elif outcome["transport"] != "failed" or not isinstance(error, str) or not error:
        raise ValueError("Invalid chart transport outcome")
    if right is None:
        report = {
            "protocol": index_prices.PROTOCOL,
            "kind": "real_index_vendor_comparison_diagnostic",
            "research_result": False,
            "symbol": plan.symbol,
            "error": error,
            "close_comparator_ready": False,
            "close_comparator": None,
            "eligible_for_execution": False,
            "historical_availability_validated": False,
            "independent_gold": False,
        }
    else:
        report = compare(plan, left, right)
    return {"KBS": left, "Vietcap": right}, report


def csv_bytes(rows, fields):
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode()


def exports(report):
    curve = report["close_comparator"]["curve"] if report["close_comparator_ready"] else []
    return {
        "field_mismatches.csv": csv_bytes(
            report.get("field_mismatches", []),
            ["session_date", "field", "KBS", "Vietcap", "KBS_minus_Vietcap"],
        ),
        "close_comparator.csv": csv_bytes(
            curve, ["session_date", "close", "base_100", "close_to_previous_return"]
        ),
    }


def capture(root, config_bytes, kbs_run, *, fetcher=fetch_chart):
    root = root.resolve()
    plan = IndexPlan.model_validate_json(config_bytes)
    if plan.end >= datetime.now(VN_OFFSET).date().isoformat():
        raise ValueError("Require a completed past end date")
    left, binding = kbs_source(root, kbs_run, plan)
    body = canonical(request_body(plan))
    folder = base_for(root) / (datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ-") + uuid4().hex[:8])
    folder.mkdir(parents=True)
    (folder / "config.json").write_bytes(config_bytes)
    (folder / "request.json").write_bytes(body)
    (folder / "index_prices.py").write_bytes(Path(index_prices.__file__).read_bytes())
    (folder / "index_crosscheck.py").write_bytes(Path(__file__).read_bytes())
    try:
        raw, metadata = fetcher(body)
        validate_http(metadata)
    except (OSError, ValueError) as exc:
        write_json(folder / "outcome.json", {"transport": "failed", "error": str(exc)})
    else:
        (folder / "response.raw").write_bytes(raw)
        write_json(
            folder / "http.json",
            {k: metadata[k] for k in ("source_url", "final_url", "http_status", "retrieved_at")}
            | {"content_type": metadata.get("content_type")},
        )
        write_json(folder / "outcome.json", {"transport": "captured", "error": None})
    normalized, report = derive(folder, plan, left)
    write_json(folder / "normalized.json", normalized)
    write_json(folder / "comparison.json", report)
    for name, data in exports(report).items():
        (folder / name).write_bytes(data)
    write_json(
        folder / "manifest.json",
        {
            "protocol": index_prices.PROTOCOL,
            "kind": report["kind"],
            "research_result": False,
            "config_sha256": file_sha(folder / "config.json"),
            "request_sha256": file_sha(folder / "request.json"),
            "KBS_source_binding": binding,
            "Vietcap_source_url": index_prices.VIETCAP_URL,
            "method": "read_only_chart_POST; no_authentication_order_or_account_API; no_retry",
            "code_hashes": {
                n: file_sha(folder / n) for n in ("index_prices.py", "index_crosscheck.py")
            },
        },
    )
    write_json(
        folder / "integrity.json",
        {"files": {p.name: file_sha(p) for p in folder.iterdir() if p.is_file()}},
    )
    return folder, report


def replay(root, folder):
    root, folder = root.resolve(), Path(folder).absolute()
    if (
        folder.is_symlink()
        or folder.parent != base_for(root)
        or folder.resolve().parent != base_for(root)
    ):
        raise ValueError("Replay must select an index crosscheck in project outputs")
    seal = json.loads((folder / "integrity.json").read_bytes())
    outcome = json.loads((folder / "outcome.json").read_bytes())
    required = {
        "config.json",
        "request.json",
        "index_prices.py",
        "index_crosscheck.py",
        "outcome.json",
        "normalized.json",
        "comparison.json",
        "field_mismatches.csv",
        "close_comparator.csv",
        "manifest.json",
    }
    if outcome["transport"] == "captured":
        required.update({"response.raw", "http.json"})
    if set(seal["files"]) != required or {p.name for p in folder.iterdir()} != required | {
        "integrity.json"
    }:
        raise ValueError("Index snapshot required file set differs")
    for name, digest in seal["files"].items():
        path = folder / name
        if path.is_symlink() or path.resolve().parent != folder or file_sha(path) != digest:
            raise ValueError("Index snapshot checksum differs")
    plan = IndexPlan.model_validate_json((folder / "config.json").read_bytes())
    manifest = json.loads((folder / "manifest.json").read_bytes())
    left, binding = kbs_source(root, manifest["KBS_source_binding"]["run_id"], plan)
    if (
        manifest["KBS_source_binding"] != binding
        or manifest["protocol"] != index_prices.PROTOCOL
        or manifest["kind"] != "real_index_vendor_comparison_diagnostic"
        or manifest["research_result"] is not False
        or manifest["config_sha256"] != file_sha(folder / "config.json")
        or manifest["request_sha256"] != file_sha(folder / "request.json")
        or (folder / "request.json").read_bytes() != canonical(request_body(plan))
        or manifest["Vietcap_source_url"] != index_prices.VIETCAP_URL
        or manifest["code_hashes"]
        != {n: file_sha(folder / n) for n in ("index_prices.py", "index_crosscheck.py")}
    ):
        raise ValueError("Index snapshot source binding or provenance differs")
    normalized, report = derive(folder, plan, left)
    if normalized != json.loads((folder / "normalized.json").read_bytes()) or report != json.loads(
        (folder / "comparison.json").read_bytes()
    ):
        raise ValueError("Recomputed index comparison differs")
    for name, data in exports(report).items():
        if data != (folder / name).read_bytes():
            raise ValueError("Recomputed index CSV differs")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--capture", action="store_true")
    group.add_argument("--replay", type=Path)
    parser.add_argument("--config", type=Path)
    parser.add_argument("--kbs-run")
    args = parser.parse_args()
    if args.replay:
        if args.config or args.kbs_run:
            parser.error("Replay uses saved sources/config; omit overrides")
        folder, report = args.replay, replay(args.root, args.replay)
    else:
        if not args.kbs_run:
            parser.error("Capture requires --kbs-run")
        config = args.config or args.root / "configs/market_index_crosscheck_v0_1.json"
        folder, report = capture(args.root, config.read_bytes(), args.kbs_run)
    print(
        json.dumps(
            {
                "path": str(folder),
                "close_comparator_ready": report["close_comparator_ready"],
                "eligible_for_execution": False,
                "research_result": False,
                "field_statistics": report.get("field_statistics"),
                "error": report.get("error"),
            }
        )
    )
    return 0 if report["close_comparator_ready"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
