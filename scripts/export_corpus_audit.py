"""Export metadata-only raw inventory and checks against the unchanged frozen pilot."""

import argparse
import hashlib
import json
import sqlite3
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

from pit_haf.data.evidence import EvidencePage
from pit_haf.data.snapshots import SnapshotStore


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sources", type=Path, required=True)
    parser.add_argument("--summary", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--root", type=Path, default=Path("data/cache/evidence"))
    parser.add_argument("--pilot-index", type=Path, default=Path("data/pilot/snapshot_index.json"))
    parser.add_argument("--pilot-summary", type=Path, default=Path(
        "outputs/milestone-1/data-pilot/20261017-final-offline/summary.json"))
    args = parser.parse_args()
    config = json.loads(args.sources.read_text(encoding="utf-8"))
    raw_summary = args.summary.read_bytes()
    summary = json.loads(raw_summary)
    specs = {row["record_id"]: row for row in config["documents"]}
    events = {row["record_id"]: row for row in summary["documents"]}
    if set(events) != set(specs):
        raise ValueError("Final summary and source manifest have different denominators")
    store = SnapshotStore(args.root)
    with sqlite3.connect(store.database) as db:
        metadata_hashes = dict(db.execute("SELECT version_id, metadata_hash FROM versions"))
    entries, blob_sizes = [], {}
    for item in store.versions():
        if item.record_id not in specs:
            continue
        blob_sizes[item.content_hash] = len(store.read_blob(item.content_hash))
        entries.append({"metadata": item.model_dump(mode="json"),
                        "registry_metadata_sha256": metadata_hashes[item.version_id],
                        "raw_byte_count": blob_sizes[item.content_hash],
                        "active_status": events[item.record_id]["status"],
                        "active_error": events[item.record_id].get("error")})
    raw_pages = (args.summary.parent / "pages.jsonl").read_bytes()
    if sha(raw_pages) != summary["pages_sha256"]:
        raise ValueError("Final page snapshot checksum mismatch")
    active_pages = {}
    for line in raw_pages.splitlines():
        page = EvidencePage.model_validate_json(line)
        if sha(page.text.encode()) != page.text_hash:
            raise ValueError("Final page text checksum mismatch")
        active_pages[(page.version_id, page.page)] = page.text_hash
    pilot_index = json.loads(args.pilot_index.read_text(encoding="utf-8"))
    for entry in pilot_index["versions"]:
        if metadata_hashes[entry["metadata"]["version_id"]] != entry["registry_metadata_sha256"]:
            raise ValueError("Frozen pilot registry metadata changed")
    pilot_summary = json.loads(args.pilot_summary.read_text(encoding="utf-8"))
    pilot_raw = (args.pilot_summary.parent / "pages.jsonl").read_bytes()
    if sha(pilot_raw) != pilot_summary["pages_sha256"]:
        raise ValueError("Frozen pilot page file changed")
    checked = 0
    for line in pilot_raw.splitlines():
        page = EvidencePage.model_validate_json(line)
        if active_pages.get((page.version_id, page.page)) != page.text_hash:
            raise ValueError("Frozen pilot page missing or changed in active release")
        checked += 1
    common = {"created_at": datetime.now(UTC).isoformat(), "release_id": config["release_id"],
              "summary_sha256": sha(raw_summary), "research_prediction_results": False}
    inventory = {**common, "run_kind": "metadata_only_raw_acquisition_inventory",
                 "configured_records": len(specs), "registered_raw_versions": len(entries),
                 "unique_raw_blobs": len(blob_sizes),
                 "unique_raw_pdf_blobs": len({row["metadata"]["content_hash"] for row in entries
                                               if row["metadata"]["media_type"] == "application/pdf"}),
                 "unique_raw_html_blobs": len({row["metadata"]["content_hash"] for row in entries
                                                if row["metadata"]["media_type"] == "text/html"}),
                 "unique_raw_byte_count": sum(blob_sizes.values()),
                 "status_by_record": dict(Counter(row["status"] for row in events.values())),
                 "records_without_registered_version": sorted(set(specs) - {
                     row["metadata"]["record_id"] for row in entries}),
                 "notes": ["Includes parser-failed/review-excluded raw responses; not all are usable reports.",
                           "No raw PDF/HTML bytes, source text or redistribution license in this export."],
                 "versions": entries}
    source_files = [Path("src/pit_haf/data") / name for name in (
        "evidence.py", "snapshots.py", "pilot.py", "batches.py", "corpus.py", "coverage.py", "news.py")]
    verification = {**common, "run_kind": "artifact_integrity_checks_not_semantic_validation",
                    "active_page_count_verified": len(active_pages),
                    "active_pages_sha256": sha(raw_pages),
                    "frozen_pilot_registry_versions_unchanged": len(pilot_index["versions"]),
                    "frozen_pilot_page_text_hashes_unchanged": checked,
                    "frozen_pilot_index_sha256": sha(args.pilot_index.read_bytes()),
                    "source_file_sha256": {str(p.as_posix()): sha(p.read_bytes()) for p in source_files},
                    "not_validated": ["OCR/table/numeric/semantic accuracy", "Independent human gold",
                                      "Historical time/revision availability", "Predictive performance"]}
    args.output.mkdir(parents=True, exist_ok=True)
    for name, report in (("raw_inventory.json", inventory), ("verification.json", verification)):
        with (args.output / name).open("x", encoding="utf-8") as stream:
            json.dump(report, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
    print(json.dumps({"raw_versions": len(entries), "active_documents": summary["success_documents"],
                      "pilot_versions_unchanged": len(pilot_index["versions"]),
                      "pilot_pages_unchanged": checked}))


if __name__ == "__main__":
    main()
