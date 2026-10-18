import hashlib
import json

import pytest

from pit_haf.data.batches import select_batch


def test_batch_selection_reproduces_pinned_manifest_without_mutating_inputs():
    manifest = {"documents": [{"record_id": "a", "listing_url": "https://a.example/list"},
                              {"record_id": "b", "listing_url": "https://b.example/list"}],
                "sources": [{"listing_url": "https://a.example/list"},
                            {"listing_url": "https://b.example/list"}],
                "allowed_hosts": ["a.example", "b.example"], "target_documents": 2}
    batch = {"record_ids": ["b"], "allowed_hosts": ["b.example"],
             "max_document_bytes": 128 * 1024 * 1024}
    result = select_batch(manifest, batch)
    assert result["documents"] == [manifest["documents"][1]]
    assert result["sources"] == [manifest["sources"][1]]
    assert result["target_documents"] == 1
    assert manifest["target_documents"] == 2 and len(manifest["documents"]) == 2
    batch["canonical_manifest_sha256"] = hashlib.sha256(
        json.dumps(result, ensure_ascii=False, sort_keys=True).encode()
    ).hexdigest()
    assert select_batch(manifest, batch) == result
    batch["canonical_manifest_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="pinned"):
        select_batch(manifest, batch)


@pytest.mark.parametrize("change", ["unknown", "duplicate", "host", "limit"])
def test_batch_rejects_unknown_records_or_unreviewed_host_and_resource_expansion(change):
    manifest = {"documents": [{"record_id": "a", "listing_url": "https://a.example/list"}],
                "sources": [{"listing_url": "https://a.example/list"}],
                "allowed_hosts": ["a.example"]}
    batch = {"record_ids": ["a"]}
    if change == "unknown":
        batch["record_ids"] = ["missing"]
    elif change == "duplicate":
        batch["record_ids"] = ["a", "a"]
    elif change == "host":
        batch["allowed_hosts"] = ["not-reviewed.example"]
    else:
        batch["max_document_bytes"] = 129 * 1024 * 1024
    with pytest.raises(ValueError):
        select_batch(manifest, batch)
