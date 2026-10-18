"""Prepare a reproducible acquisition batch from a reviewed manifest and record-ID plan."""

import argparse
import copy
import hashlib
import json
from pathlib import Path


def select_batch(manifest: dict, batch: dict) -> dict:
    ids = batch["record_ids"]
    configured = {row["record_id"] for row in manifest["documents"]}
    if (not ids or len(ids) != len(set(ids)) or set(ids) - configured or
            len(configured) != len(manifest["documents"])):
        raise ValueError("Batch needs unique, known record IDs from a unique manifest")
    result = copy.deepcopy(manifest)
    result["documents"] = [row for row in result["documents"] if row["record_id"] in set(ids)]
    result["target_documents"] = len(ids)
    listings = {row.get("listing_url") for row in result["documents"]}
    result["sources"] = [row for row in result["sources"] if row["listing_url"] in listings]
    if "allowed_hosts" in batch:
        if set(batch["allowed_hosts"]) - set(manifest["allowed_hosts"]):
            raise ValueError("Batch cannot add hosts outside the reviewed manifest")
        result["allowed_hosts"] = batch["allowed_hosts"]
    if "max_document_bytes" in batch:
        limit = batch["max_document_bytes"]
        if type(limit) is not int or not 1 <= limit <= 128 * 1024 * 1024:
            raise ValueError("Batch response limit must be between 1 byte and 128 MiB")
        result["max_document_bytes"] = limit
    canonical = json.dumps(result, ensure_ascii=False, sort_keys=True).encode()
    if (batch.get("canonical_manifest_sha256") and
            hashlib.sha256(canonical).hexdigest() != batch["canonical_manifest_sha256"]):
        raise ValueError("Batch manifest differs from the pinned acquisition plan")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sources", type=Path, required=True)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--batch", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    manifest = json.loads(args.sources.read_text(encoding="utf-8"))
    plan = json.loads(args.plan.read_text(encoding="utf-8"))
    matches = [row for row in plan["batches"] if row["batch_id"] == args.batch]
    if len(matches) != 1:
        raise ValueError("Select exactly one known batch ID")
    result = select_batch(manifest, matches[0])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
    print(f"Prepared {len(result['documents'])} configured records: {args.output}")


if __name__ == "__main__":
    main()
