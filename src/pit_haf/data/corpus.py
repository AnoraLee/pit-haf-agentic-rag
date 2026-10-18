"""Merge disjoint acquisition batches into a verified, immutable local corpus snapshot."""

import argparse
import hashlib
import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

from pit_haf.data.evidence import EvidencePage
from pit_haf.data.gateway import deliver_as_of
from pit_haf.data.pilot import publish_summary, validate_manifest_identity
from pit_haf.data.snapshots import SnapshotStore


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def merge_snapshots(manifest_path: Path, summaries: list[Path], *, store: SnapshotStore,
                    output: Path, retry_failed_records: set[str] | None = None) -> Path:
    """Copy original page lines; reject overlaps, missing pages and changed source identities.

    Failed retries require explicit record selection and preserve the original attempt.
    Successful or reviewed versions cannot be replaced. The input snapshots stay intact.
    """
    raw_manifest = manifest_path.read_bytes()
    manifest = json.loads(raw_manifest)
    specs = {row["record_id"]: row for row in manifest["documents"]}
    if len(specs) != len(manifest["documents"]) or not summaries:
        raise ValueError("Need a unique manifest and at least one input snapshot")
    registry = {item.version_id: item for item in store.versions()}
    retry_failed_records = retry_failed_records or set()
    used_retries, attempt_history = set(), []
    events, provenance, retained_lines = {}, [], []
    for path in summaries:
        raw_summary = path.read_bytes()
        summary = json.loads(raw_summary)
        raw_pages = (path.parent / "pages.jsonl").read_bytes()
        if digest(raw_pages) != summary["pages_sha256"]:
            raise ValueError("Input page snapshot checksum mismatch")
        rows = list(summary["documents"])
        for record in summary.get("configured_records_not_registered", []):
            if any(row["record_id"] == record for row in rows):
                raise ValueError("Unregistered record also occurs in input events")
            rows.append({"record_id": record, "status": "not_acquired",
                         "error_type": "not_registered",
                         "error": "No registered version; original failure remains in acquisition ledger."})
        accepted, batch_records = {}, set()
        for row in rows:
            record = row["record_id"]
            if record not in specs or record in batch_records:
                raise ValueError("Input record is outside manifest or overlaps another batch")
            batch_records.add(record)
            if record in events:
                if (record not in retry_failed_records or record in used_retries or
                        events[record].get("status") not in {"failed", "not_acquired"} or
                        row.get("status") not in {"extracted", "failed"}):
                    raise ValueError("Overlapping record needs explicit failed retry selection")
                attempt_history.append({"record_id": record, "earlier_attempt": events[record],
                                        "replacement_summary_sha256": digest(raw_summary)})
                used_retries.add(record)
            if row.get("ticker", specs[record]["ticker"]) != specs[record]["ticker"]:
                raise ValueError("Input event ticker disagrees with manifest")
            row = {**row, "ticker": specs[record]["ticker"]}
            if row.get("status") == "extracted":
                version = registry.get(row["version_id"])
                if (version is None or version.record_id != record or
                        version.ticker != row["ticker"] or
                        version.content_hash != row["content_hash"]):
                    raise ValueError("Input event and immutable registry identity disagree")
                validate_manifest_identity(version, specs[record])
                store.read_blob(version.content_hash)
                if version.version_id in accepted:
                    raise ValueError("Duplicate accepted version")
                accepted[version.version_id] = row
            events[record] = row
        numbers, text_pages = {}, Counter()
        for line in raw_pages.splitlines():
            if not line.strip():
                continue
            page = EvidencePage.model_validate_json(line)
            row = accepted.get(page.version_id)
            version = registry.get(page.version_id)
            if (row is None or version is None or page.record_id != version.record_id or
                    page.ticker != version.ticker or page.content_hash != version.content_hash or
                    page.source_url != version.source_url or page.data_kind != version.data_kind or
                    page.related_tickers != version.related_tickers or
                    page.retrieved_at != version.retrieved_at or
                    digest(page.text.encode()) != page.text_hash):
                raise ValueError("Input page does not match accepted immutable evidence")
            expected_status = "text_present" if page.text.strip() else "no_text_ocr_not_performed"
            if page.extraction_status != expected_status:
                raise ValueError("Page text presence status disagrees with literal text")
            seen = numbers.setdefault(page.version_id, set())
            if page.page in seen:
                raise ValueError("Duplicate page in input snapshot")
            seen.add(page.page)
            text_pages[page.version_id] += bool(page.text.strip())
            retained_lines.append(line)
        for version_id, row in accepted.items():
            if (row["pages"] < 1 or numbers.get(version_id) != set(range(1, row["pages"] + 1)) or
                    text_pages[version_id] != row["text_pages"]):
                raise ValueError("Missing/non-contiguous pages or incorrect text page totals")
        if (sum(row["pages"] for row in accepted.values()) != summary["page_count"] or
                sum(row["text_pages"] for row in accepted.values()) != summary["text_page_count"]):
            raise ValueError("Input summary totals disagree with verified pages")
        provenance.append({"summary_path": str(path), "summary_sha256": digest(raw_summary),
                           "pages_sha256": digest(raw_pages), "manifest_hash": summary.get("manifest_hash"),
                           "created_at": summary["created_at"], "network_revalidation": False})
    if set(events) != set(specs):
        raise ValueError("Every configured record needs a successful, failed or excluded input event")
    if used_retries != retry_failed_records:
        raise ValueError("Every selected retry must follow exactly one failed attempt")
    rows = [events[record] for record in specs]
    successful = [row for row in rows if row.get("status") == "extracted"]
    active_ids = {row["version_id"] for row in successful}
    cutoff = datetime.now(UTC).isoformat()
    strict = deliver_as_of(store, decision_at=cutoff)
    payload = b"\n".join(retained_lines) + (b"\n" if retained_lines else b"")
    result = {
        "run_kind": ("merged_development_corpus_snapshot" if all(
            spec.get("data_kind", "real_document") == "real_document" for spec in specs.values()
        ) else "test_fixture"), "created_at": cutoff,
        "release_id": manifest.get("release_id"), "network_requests": 0,
        "research_prediction_results": False, "historical_availability_inferred": False,
        "manifest_hash": digest(raw_manifest), "input_snapshots": provenance,
        "explicit_failed_retries": sorted(used_retries), "earlier_failed_attempts": attempt_history,
        "configured_documents": len(specs), "target_documents": manifest["target_documents"],
        "success_documents": len(successful), "failed_documents": len(specs) - len(successful),
        "success_by_ticker": dict(Counter(row["ticker"] for row in successful)),
        "target_shortfall": max(0, manifest["target_documents"] - len(successful)),
        "registered_versions": sum(bool(row.get("version_id")) for row in rows),
        "curation_excluded_documents": sum(row.get("status") == "curation_excluded" for row in rows),
        "parser_failed_documents": sum(row.get("status") == "failed" and bool(row.get("version_id"))
                                       for row in rows),
        "page_count": sum(row["pages"] for row in successful),
        "text_page_count": sum(row["text_pages"] for row in successful),
        "empty_page_count_no_ocr": sum(row["pages"] - row["text_pages"] for row in successful),
        "strict_gateway_deliveries": sum(d.evidence.version_id in active_ids for d in strict.deliveries),
        "pages_sha256": digest(payload), "pages_file": str((output / "pages.jsonl").resolve()),
        "documents": rows,
        "limitations": ["Original input page lines copied without re-extraction or text normalization.",
                        "No remote revision check for reused inputs; see original acquisition history.",
                        "No OCR, independent human labels or historical time/revision proof added.",
                        "Current issuer/access selection is not a historical investment universe."],
    }
    output.mkdir(parents=True, exist_ok=False)
    (output / "sources.json").write_bytes(raw_manifest)
    (output / "pages.jsonl").write_bytes(payload)
    publish_summary(output, result)
    return output / "summary.json"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sources", type=Path, required=True)
    parser.add_argument("--summary", type=Path, action="append", required=True)
    parser.add_argument("--root", type=Path, default=Path("data/cache/evidence"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--retry-failed-record", action="append", default=[])
    args = parser.parse_args()
    path = merge_snapshots(args.sources, args.summary, store=SnapshotStore(args.root), output=args.output,
                           retry_failed_records=set(args.retry_failed_record))
    print(path)


if __name__ == "__main__":
    main()
