"""Import pinned publisher-text mirrors with joined provenance; never claim raw HTML proof."""

import argparse
import csv
import hashlib
import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlsplit

from pit_haf.data.evidence import EvidencePage, EvidenceVersion, version_id_for
from pit_haf.data.hub import file_sha
from pit_haf.data.news import link_tickers, normalize_url, publication_fields
from pit_haf.data.pilot import publish_summary
from pit_haf.data.snapshots import SnapshotStore, canonical

EXTRACTOR = "dataset-csv/1;provided-publisher-text;not-original-html;no-new-ocr"


def text_key(value):
    return hashlib.sha256(" ".join(value.split()).casefold().encode()).hexdigest()


def import_dataset(config: dict, *, input_root: Path, store: SnapshotStore, output: Path,
                   exclude_urls: set[str] | None = None) -> dict:
    """Output is published only after completion; reruns reuse immutable registered versions."""
    output.mkdir(parents=True, exist_ok=False)
    csv.field_size_limit(2 * 1024 * 1024)
    specs = {f["path"]: f for f in config["files"]}
    verified = {}
    for name in ["processed/news_metadata.csv", *[f"processed/{s}.csv" for s in config["splits"]]]:
        path = input_root / name
        if path.exists():
            spec = specs[name]
            if path.stat().st_size != spec["size"] or file_sha(path) != spec["sha256"]:
                raise ValueError("Pinned input checksum mismatch: " + name)
            verified[name] = spec
    if "processed/news_metadata.csv" not in verified:
        raise ValueError("Full metadata join file is required")
    metadata = {}
    with (input_root / "processed/news_metadata.csv").open(encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream):
            if row["id"] in metadata:
                raise ValueError("Dataset metadata IDs are not unique")
            metadata[row["id"]] = row
    descriptor = {"dataset_id": config["dataset_id"], "revision": config["dataset_revision"],
                  "verified_source_files": verified, "license_observed": config["license_observed"],
                  "dataset_source_url": config["dataset_url"], "not_original_publisher_html": True}
    listing_hash = store.put_blob(canonical(descriptor))
    prior = {v.version_id: v for v in store.versions()}
    seen_urls = set(exclude_urls or ())
    seen_text, seen_ids = set(), set()
    accepted, failures, manifest, counts = [], [], [], Counter()
    observed = datetime.now(UTC).isoformat()
    hosts = set(config["allowed_original_hosts"])
    target = config["target_documents"]
    pages_path = output / "pages.jsonl"
    with pages_path.open("x", encoding="utf-8", newline="\n") as pages:
        for split in config["splits"]:
            name = f"processed/{split}.csv"
            if name not in verified:
                continue
            with (input_root / name).open(encoding="utf-8-sig", newline="") as source:
                for row in csv.DictReader(source):
                    counts["scanned_rows"] += 1
                    if row.get("category") not in config["categories"]:
                        counts["outside_categories"] += 1
                        continue
                    counts["domain_candidate_rows"] += 1
                    original = metadata.get(row.get("id"))
                    try:
                        if original is None or original["category"] != row["category"]:
                            raise ValueError("Missing/conflicting ID/category metadata join")
                        if row["id"] in seen_ids:
                            raise ValueError("Repeated source ID across classification splits")
                        seen_ids.add(row["id"])
                        locator = normalize_url(original["url"], "", hosts)
                        if urlsplit(locator).path in {"", "/"}:
                            raise ValueError("Original article locator is missing")
                        title, lede, body = (str(row.get(k) or "").strip() for k in ("title", "description", "content"))
                        if len(title) < 10 or not config["min_body_chars"] <= len(body) <= config["max_body_chars"]:
                            raise ValueError("Empty/short/large publisher content")
                        fingerprint = text_key(body)
                        if locator in seen_urls or fingerprint in seen_text:
                            counts["duplicate_url_or_body"] += 1
                            continue
                        dates = publication_fields([{"origin": "dataset_metadata:public_date", "value": original["public_date"]}])
                        if not dates.get("publication_date"):
                            raise ValueError("Original publication date could not be parsed")
                        if dates["publication_date"] > observed[:10]:
                            raise ValueError("Observed publication date is in the future")
                        record = "MIRROR-NEWS-" + hashlib.sha256((config["dataset_id"] + "\0" + locator).encode()).hexdigest()[:24]
                        payload = canonical({"dataset": descriptor["dataset_id"], "revision": descriptor["revision"],
                                             "dataset_path": name, "dataset_split": split,
                                             "article_row": row, "source_metadata_row": original})
                        digest = store.put_blob(payload)
                        version_id = version_id_for(record, digest)
                        tickers = link_tickers(title, lede, config["ticker_aliases"])
                        spec = {"record_id": record, "source_id": "vietonlinenews",
                                "source_url": locator, "ticker": tickers[0] if tickers else "MARKET",
                                "related_tickers": list(tickers), "document_type": "news_article",
                                "title": title, "publisher": original["source"], "author": original.get("author") or None,
                                "media_type": "application/json", "origin": "dataset_mirror",
                                "dataset_id": descriptor["dataset_id"], "dataset_revision": descriptor["revision"],
                                "dataset_path": name, "dataset_row_id": row["id"], "dataset_split": split,
                                "listing_url": config["dataset_url"], "statement_scope": "not_applicable",
                                "evidence_scope": "issuer" if tickers else "market",
                                "reporting_period": dates["publication_date"][:4],
                                "entity_linking_basis": "title_and_lede_alias_match;not_human_gold",
                                "rights_note": config["rights_note"], "data_kind": config.get("data_kind", "real_document"), **dates}
                        version = prior.get(version_id)
                        if version is None:
                            version = EvidenceVersion(**spec, version_id=version_id, content_hash=digest,
                                                      retrieved_at=observed, system_recorded_at=datetime.now(UTC),
                                                      listing_snapshot_hash=listing_hash)
                            store.register(version)
                        else:
                            if (version.source_url != locator or version.origin != "dataset_mirror" or
                                    version.dataset_revision != descriptor["revision"]):
                                raise ValueError("Pinned dataset reuse identity mismatch")
                            store.read_blob(digest)
                        model = version.model_dump(mode="json")
                        spec = {key: model[key] for key in spec}
                        text = title + "\n\n" + (lede + "\n\n" if lede and lede not in body else "") + body
                        page = EvidencePage(record_id=record, version_id=version_id, ticker=version.ticker,
                                            related_tickers=version.related_tickers, content_hash=digest, page=1,
                                            text=text, text_hash=hashlib.sha256(text.encode()).hexdigest(),
                                            source_url=locator, retrieved_at=version.retrieved_at, extractor=EXTRACTOR,
                                            extraction_status="text_present", data_kind=version.data_kind)
                        pages.write(page.model_dump_json() + "\n")
                        event = {"record_id": record, "version_id": version_id, "ticker": version.ticker,
                                 "content_hash": digest, "status": "extracted", "pages": 1, "text_pages": 1,
                                 "dataset_row_id": row["id"], "dataset_split": split,
                                 "body_sha256_normalized": fingerprint, "original_url": locator}
                        accepted.append(event)
                        manifest.append(spec)
                        seen_urls.add(locator)
                        seen_text.add(fingerprint)
                        store.log_acquisition({"kind": "dataset_mirror_import", **event})
                        if len(accepted) % 500 == 0:
                            progress = {"accepted": len(accepted), "target": target, "counts": dict(counts)}
                            (output / "progress.json").write_text(json.dumps(progress), encoding="utf-8")
                            print(json.dumps(progress), flush=True)
                        if len(accepted) >= target:
                            break
                    except (ValueError, KeyError) as exc:
                        failures.append({"row_id": row.get("id"), "split": split,
                                         "error_type": type(exc).__name__, "error": str(exc)})
                if len(accepted) >= target:
                    break
    manifest_config = {"release_id": config["release_id"], "target_documents": len(manifest),
                       "allowed_hosts": sorted(hosts), "sources": [{"source_id": "vietonlinenews", "listing_url": config["dataset_url"]}],
                       "documents": manifest}
    raw_manifest = canonical(manifest_config)
    (output / "sources.json").write_bytes(raw_manifest)
    (output / "rejected_rows.json").write_text(json.dumps(failures, ensure_ascii=False, indent=2), encoding="utf-8")
    result = {"run_kind": "real_dataset_mirror_import" if config.get("data_kind", "real_document") == "real_document" else "test_fixture",
              "created_at": datetime.now(UTC).isoformat(), "research_prediction_results": False,
              "network_requests": 0, "manifest_hash": hashlib.sha256(raw_manifest).hexdigest(),
              "source_descriptor_hash": listing_hash, "selection_config": config,
              "selection_counts": dict(counts), "rejected_candidate_rows": len(failures),
              "configured_documents": len(manifest), "target_documents": target,
              "success_documents": len(accepted), "failed_documents": 0,
              "target_shortfall": max(0, target - len(accepted)),
              "page_count": len(accepted), "text_page_count": len(accepted), "empty_page_count_no_ocr": 0,
              "strict_gateway_deliveries": 0, "historical_availability_inferred": False,
              "pages_file": str(pages_path.resolve()), "pages_sha256": file_sha(pages_path),
              "documents": accepted, "success_by_ticker": dict(Counter(e["ticker"] for e in accepted)),
              "limitations": ["Raw snapshots are serialized dataset rows, not downloaded publisher HTML.",
                              "Dataset category/date/text are third-party observations, not reviewed historical proof.",
                              "Input classification splits are provenance only; no financial evaluation split frozen.",
                              "Full text remains local; dataset license other/empty file establishes no redistribution right."]}
    publish_summary(output, result)
    print(json.dumps({"accepted": len(accepted), "shortfall": result["target_shortfall"], "counts": dict(counts)}))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--input-root", type=Path, required=True)
    parser.add_argument("--root", type=Path, default=Path("data/cache/evidence"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    store = SnapshotStore(args.root)
    config = json.loads(args.config.read_text(encoding="utf-8"))
    excluded = {v.source_url for v in store.versions() if (
        v.origin != "dataset_mirror" or v.dataset_id != config["dataset_id"] or
        v.dataset_revision != config["dataset_revision"])}
    import_dataset(config, input_root=args.input_root, store=store, output=args.output, exclude_urls=excluded)


if __name__ == "__main__":
    main()
