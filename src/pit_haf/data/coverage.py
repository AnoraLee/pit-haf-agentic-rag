"""Export release metadata and honest coverage gaps without publishing raw documents."""

import argparse
import copy
import hashlib
import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from pit_haf.data.evidence import EvidencePage
from pit_haf.data.gateway import deliver_as_of
from pit_haf.data.pilot import publish_summary
from pit_haf.data.snapshots import SnapshotStore


def build_release(store: SnapshotStore, summary: dict, universe: dict) -> tuple[dict, dict]:
    tickers = [item["ticker"] for item in universe["issuers"]]
    years = universe["target_annual_years"]
    if len(set(tickers)) != len(tickers) or len(set(years)) != len(years):
        raise ValueError("Duplicate issuer/year targets would distort coverage")
    successful_rows = [row for row in summary["documents"] if row.get("status") == "extracted"]
    successful = {row["version_id"]: row for row in successful_rows}
    if len(successful) != len(successful_rows):
        raise ValueError("Duplicate versions in the acquisition summary")
    versions = {item.version_id: item for item in store.versions()
                if item.version_id in successful and item.data_kind == "real_document"}
    if set(versions) != set(successful):
        raise ValueError("Successful document identity is missing or includes fixtures")
    if {item.ticker for item in versions.values()} - set(tickers):
        raise ValueError("Acquired issuer is outside the declared universe")
    if (sum(row["pages"] for row in successful_rows) != summary["page_count"] or
        sum(row["text_pages"] for row in successful_rows) != summary["text_page_count"]):
        raise ValueError("Summary totals disagree with document page coverage")
    with sqlite3.connect(store.database) as db:
        hashes = dict(db.execute("SELECT version_id, metadata_hash FROM versions"))
    eligible = {delivery.evidence.version_id for delivery in deliver_as_of(
        store, decision_at=summary["created_at"]
    ).deliveries} & set(versions)
    entries = []
    for version in versions.values():
        store.read_blob(version.content_hash)
        row = successful[version.version_id]
        if row["record_id"] != version.record_id or row["ticker"] != version.ticker:
            raise ValueError("Summary and registry document identity disagree")
        page_status = {key: row[key] for key in (
            "record_id", "version_id", "ticker", "content_hash", "status", "pages", "text_pages"
        )}
        page_status.update({key: row.get(key) for key in (
            "parser_warning_count", "potentially_partial_text_pages", "potentially_partial_document"
        )})
        entries.append({"metadata": version.model_dump(mode="json"),
                        "registry_metadata_sha256": hashes[version.version_id],
                        "page_status": page_status})
    by_ticker, gaps = [], []
    for issuer in universe["issuers"]:
        documents = [item for item in versions.values() if item.ticker == issuer["ticker"]]
        present = {item.reporting_period for item in documents if item.document_type == "annual_report"}
        annual = {str(year): str(year) in present for year in years}
        gaps.extend({"ticker": issuer["ticker"], "year": year, "kind": "annual_report"}
                    for year in years if not annual[str(year)])
        page_stats = [successful[item.version_id] for item in documents]
        by_ticker.append({**issuer, "documents": len(documents),
                          "logical_records": len({item.record_id for item in documents}),
                          "pages": sum(item["pages"] for item in page_stats),
                          "text_pages": sum(item["text_pages"] for item in page_stats),
                          "annual_years": annual,
                          "strict_eligible": sum(item.version_id in eligible for item in documents)})
    coverage = {
        "release_id": universe["release_id"], "run_kind": "development_corpus_coverage",
        "created_at": summary["created_at"], "research_prediction_results": False,
        "configured_documents": summary["configured_documents"],
        "registered_versions": summary.get("registered_versions", len({
            row["version_id"] for row in summary["documents"] if row.get("version_id")
        })),
        "acquired_documents": len(versions),
        "failed_documents": summary["configured_documents"] - len({v.record_id for v in versions.values()}),
        "parser_failed_documents": summary.get("parser_failed_documents", summary["failed_documents"]),
        "curation_excluded_documents": summary.get("curation_excluded_documents", 0),
        "configured_records_not_registered": summary.get("configured_records_not_registered", []),
        "target_issuers": len(tickers), "observed_issuers": len({v.ticker for v in versions.values()}),
        "observed_broad_sectors": len({row["sector"] for row in by_ticker if row["documents"]}),
        "target_annual_cells": len(tickers) * len(years),
        "covered_annual_cells": len(tickers) * len(years) - len(gaps),
        "page_count": summary["page_count"], "text_page_count": summary["text_page_count"],
        "empty_page_count_no_ocr": summary["empty_page_count_no_ocr"],
        "documents_with_parser_warnings": sum(bool(row.get("parser_warning_count"))
                                              for row in successful_rows),
        "documents_with_potentially_partial_text": sum(bool(
            row.get("potentially_partial_text_pages") or row.get("potentially_partial_document")
        ) for row in successful_rows),
        "strict_eligible_documents": len(eligible), "issuers": by_ticker,
        "missing_annual_cells": gaps,
        "failures": [{key: row.get(key) for key in ("record_id", "ticker", "error_type", "error")}
                     for row in summary["documents"] if row.get("status") != "extracted"] + [
                         {"record_id": record, "error_type": "not_registered",
                          "error": "No acquired version; original acquisition failure remains in ledger."}
                         for record in summary.get("configured_records_not_registered", [])
                     ],
        "limitations": [
            "Broad sector labels are curated, not an official historical index classification.",
            "Current issuer/access selection; historical membership and survivorship not validated.",
            "Annual ticker-year coverage counts a translation or revision only once.",
            "Text presence is not OCR/table/numeric/semantic fidelity.",
            "Missing time/version proof remains quarantined; no prediction/backtest or gold labels.",
        ],
    }
    index = {
        "schema_version": "corpus_snapshot_index_v0.2", "release_id": universe["release_id"],
        "raw_store_relative_path": "data/cache/evidence", "total_versions": len(entries),
        "strict_deliveries": len(eligible),
        "historical_availability_validated": bool(entries) and len(eligible) == len(entries),
        "notes": ["Metadata/hash export only. Raw PDFs/pages are local ignored artifacts.",
                  "registry_metadata_sha256 covers original immutable JSON, before derived defaults."],
        "versions": entries,
    }
    return index, coverage


def curate_snapshot(summary_path: Path, output: Path, policy_path: Path) -> Path:
    """Exclude reviewed exact byte versions, retaining failed cases and original snapshots."""
    raw_summary = summary_path.read_bytes()
    summary = json.loads(raw_summary)
    raw_pages = (summary_path.parent / "pages.jsonl").read_bytes()
    if hashlib.sha256(raw_pages).hexdigest() != summary["pages_sha256"]:
        raise ValueError("Page snapshot checksum mismatch")
    policy_bytes = policy_path.read_bytes()
    policy = json.loads(policy_bytes)
    excluded = {}
    for rule in policy["exclude_versions"]:
        matches = [row for row in summary["documents"] if (
            row.get("version_id") == rule["version_id"] and row.get("content_hash") == rule["content_hash"]
            and row.get("record_id") == rule["record_id"] and row.get("status") == "extracted"
        )]
        if len(matches) != 1 or rule["version_id"] in excluded:
            raise ValueError("Curation rule must identify exactly one successful immutable version")
        excluded[rule["version_id"]] = rule
    output.mkdir(parents=True, exist_ok=False)
    retained = []
    for line in raw_pages.splitlines():
        if line.strip():
            page = EvidencePage.model_validate_json(line)
            if page.version_id not in excluded:
                retained.append(line)
    pages_bytes = b"\n".join(retained) + (b"\n" if retained else b"")
    (output / "pages.jsonl").write_bytes(pages_bytes)
    (output / "curation.json").write_bytes(policy_bytes)
    if (summary_path.parent / "sources.json").is_file():
        (output / "sources.json").write_bytes((summary_path.parent / "sources.json").read_bytes())
    result = copy.deepcopy(summary)
    for row in result["documents"]:
        if row.get("version_id") in excluded:
            row.update(status="curation_excluded", error_type="reviewed_source_exclusion",
                       error=excluded[row["version_id"]]["reason"])
    accepted = [row for row in result["documents"] if row.get("status") == "extracted"]
    result.update(
        run_kind="curated_development_corpus_snapshot", network_requests=0,
        research_prediction_results=False,
        source_summary_sha256=hashlib.sha256(raw_summary).hexdigest(),
        source_pages_sha256=hashlib.sha256(raw_pages).hexdigest(),
        curation_policy_sha256=hashlib.sha256(policy_bytes).hexdigest(),
        curation_created_at=datetime.now(UTC).isoformat(),
        curation_excluded_documents=len(excluded), parser_failed_documents=summary["failed_documents"],
        success_documents=len({row["record_id"] for row in accepted}),
        failed_documents=summary["configured_documents"]-len({row["record_id"] for row in accepted}),
        page_count=sum(row["pages"] for row in accepted),
        text_page_count=sum(row["text_pages"] for row in accepted),
        empty_page_count_no_ocr=sum(row["pages"]-row["text_pages"] for row in accepted),
        pages_file=str((output / "pages.jsonl").resolve()),
        pages_sha256=hashlib.sha256(pages_bytes).hexdigest(),
        target_shortfall=max(0, summary["target_documents"]-len({row["record_id"] for row in accepted})),
        strict_gateway_deliveries=None,
        strict_eligibility_note="Recomputed for retained versions in release coverage/index export.",
        success_by_ticker={ticker:sum(row["ticker"] == ticker for row in accepted)
                           for ticker in sorted({row["ticker"] for row in accepted})},
    )
    publish_summary(output, result)
    return output / "summary.json"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--summary", type=Path, required=True)
    parser.add_argument("--universe", type=Path, required=True)
    parser.add_argument("--root", type=Path, default=Path("data/cache/evidence"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--curation", type=Path)
    parser.add_argument("--curated-output", type=Path)
    args = parser.parse_args()
    if bool(args.curation) != bool(args.curated_output):
        parser.error("--curation and --curated-output must be used together")
    if args.curation:
        args.summary = curate_snapshot(args.summary, args.curated_output, args.curation)
    summary = json.loads(args.summary.read_text(encoding="utf-8"))
    raw = (args.summary.parent / "pages.jsonl").read_bytes()
    if hashlib.sha256(raw).hexdigest() != summary["pages_sha256"]:
        raise ValueError("Page snapshot checksum mismatch")
    universe_bytes = args.universe.read_bytes()
    index, coverage = build_release(SnapshotStore(args.root), summary, json.loads(universe_bytes))
    for report in (index, coverage):
        report.update(summary_sha256=hashlib.sha256(args.summary.read_bytes()).hexdigest(),
                      universe_sha256=hashlib.sha256(universe_bytes).hexdigest())
    args.output.mkdir(parents=True, exist_ok=True)
    for name, report in (("snapshot_index.json", index), ("coverage.json", coverage)):
        with (args.output / name).open("x", encoding="utf-8") as stream:
            json.dump(report, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
    print(json.dumps({key: coverage[key] for key in (
        "acquired_documents", "observed_issuers", "covered_annual_cells",
        "target_annual_cells", "page_count", "strict_eligible_documents"
    )}))


if __name__ == "__main__":
    main()
