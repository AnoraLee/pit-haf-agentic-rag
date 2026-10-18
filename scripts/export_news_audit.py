"""Export news discovery/acquisition metadata and exact-body duplicate diagnostics, never text."""

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

from pit_haf.data.snapshots import SnapshotStore


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--discovery", type=Path, action="append", required=True)
    parser.add_argument("--original-discovery", type=Path, action="append", default=[])
    parser.add_argument("--summary", type=Path, action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--root", type=Path, default=Path("data/cache/evidence"))
    args = parser.parse_args()
    candidates, resources, duplicates, provenance, selections = [], [], [], [], []
    events, seen = [], set()
    for path in args.discovery:
        data = json.loads(path.read_text(encoding="utf-8"))
        for row in data["candidates"]:
            if row["record_id"] in seen:
                raise ValueError("Discovery batches overlap")
            seen.add(row["record_id"])
            candidates.append(row)
        resources.extend(data["resources"])
        duplicates.extend(data["duplicate_discovery_links"])
        selections.append(data["config"])
        provenance.append({"kind": "discovery", "path": path.as_posix(), "sha256": sha(path),
                           "earlier_discovery_sha256": data.get("source_discovery_sha256")})
    for path in args.summary:
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("research_prediction_results") or data.get("run_kind") == "test_fixture":
            raise ValueError("News release must contain observed real data only")
        if sha(path.parent / "pages.jsonl") != data["pages_sha256"]:
            raise ValueError("News section snapshot checksum mismatch")
        events.extend(data["documents"])
        provenance.append({"kind": "news_snapshot", "path": path.as_posix(), "sha256": sha(path),
                           "pages_sha256": data["pages_sha256"], "extractor": data.get("extractor"),
                           "source_summary_sha256": data.get("source_summary_sha256"),
                           "source_pages_sha256": data.get("source_pages_sha256"),
                           "extraction_text_changes": data.get("extraction_text_changes", [])})
    original_discovery_configs = []
    for path in args.original_discovery:
        original = json.loads(path.read_text(encoding="utf-8"))
        if not {r["record_id"] for r in original["candidates"]} <= seen:
            raise ValueError("Original discovery contains candidates outside the reviewed selection")
        original_discovery_configs.append({"path": path.as_posix(), "sha256": sha(path),
                                           "created_at": original["created_at"], "config": original["config"]})
    if len(events) != len(seen) or {e["record_id"] for e in events} != seen:
        raise ValueError("Discovery and acquisition denominators disagree")
    store = SnapshotStore(args.root)
    versions = {v.version_id: v for v in store.versions()}
    accepted = [e for e in events if e["status"] == "extracted"]
    body_groups = defaultdict(list)
    for event in accepted:
        if versions[event["version_id"]].data_kind != "real_document":
            raise ValueError("Fixture in news release")
        body_groups[event["body_sha256"]].append(event["record_id"])
    metadata = [versions[e["version_id"]] for e in accepted]
    report = {
        "schema_version": "public_news_audit_v0.4", "research_prediction_results": False,
        "candidate_urls": len(candidates), "accepted_article_urls": len(accepted),
        "failed_article_urls": len(events) - len(accepted),
        "articles_by_source": dict(Counter(versions[e["version_id"]].source_id for e in accepted)),
        "articles_by_type": dict(Counter(v.document_type for v in metadata)),
        "articles_by_primary_ticker": dict(Counter(v.ticker for v in metadata)),
        "related_ticker_article_counts": dict(Counter(t for v in metadata for t in v.related_tickers)),
        "timestamp_precision_counts": dict(Counter(v.timestamp_precision for v in metadata)),
        "distinct_body_hashes": len(body_groups),
        "exact_body_duplicate_groups": [{"body_sha256": h, "record_ids": sorted(ids)}
                                         for h, ids in sorted(body_groups.items()) if len(ids) > 1],
        "source_selection": selections, "original_discovery_configs": original_discovery_configs,
        "provenance": provenance,
        "discovery_resources": resources, "duplicate_discovery_links": duplicates,
        "candidates": candidates, "acquisition_events": events,
        "limitations": ["URL dedup and body SHA-256 are not semantic/syndication deduplication.",
                        "RSS/listing snapshots are access/time biased; no historical evaluation split.",
                        "Publisher/ticker/date strings are observations, not independent human gold.",
                        "No raw HTML/PDF/article text, HTTP credentials or redistribution rights exported.",
                        "No reviewed historical time/revision proof; strict eligibility remains separate."],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    print(json.dumps({k: report[k] for k in ("candidate_urls", "accepted_article_urls", "distinct_body_hashes")}))


if __name__ == "__main__":
    main()
