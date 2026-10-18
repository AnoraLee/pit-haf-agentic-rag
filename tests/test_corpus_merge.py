"""Batching must preserve literal evidence, failures and the configured denominator."""

import copy
import hashlib
import json

import pytest

from pit_haf.data.corpus import merge_snapshots
from pit_haf.data.evidence import EvidencePage, EvidenceVersion, version_id_for
from pit_haf.data.snapshots import SnapshotStore


def setup_batches(tmp_path):
    store = SnapshotStore(tmp_path / "store")
    specs, paths, originals = [], [], []
    for i in range(2):
        record = f"FPT-synthetic-{i}"
        raw_hash = store.put_blob(f"Synthetic fixture bytes {i}".encode())
        spec = {"record_id": record, "source_id": "synthetic", "ticker": "FPT",
                "source_url": f"https://fixture.example/{i}.pdf", "title": "Synthetic batch fixture",
                "document_type": "financial_statement", "reporting_period": f"2024-Q{i+1}",
                "data_kind": "test_fixture"}
        item = EvidenceVersion(**spec, version_id=version_id_for(record, raw_hash),
                               content_hash=raw_hash, retrieved_at="2026-10-17T10:00:00Z",
                               system_recorded_at="2026-10-17T10:01:00Z")
        store.register(item)
        text = f"Synthetic fixture text {i}"
        page = EvidencePage(record_id=record, version_id=item.version_id, ticker="FPT",
                            content_hash=raw_hash, source_url=item.source_url, page=1, text=text,
                            text_hash=hashlib.sha256(text.encode()).hexdigest(),
                            retrieved_at=item.retrieved_at, extractor="synthetic-fixture",
                            data_kind="test_fixture", extraction_status="text_present")
        # Intentional JSON spacing: merge must preserve these bytes as well as text hashes.
        payload = json.dumps(page.model_dump(mode="json"), indent=None).encode() + b"\n"
        folder = tmp_path / f"batch{i}"
        folder.mkdir()
        (folder / "pages.jsonl").write_bytes(payload)
        row = {"record_id": record, "version_id": item.version_id, "ticker": "FPT",
               "content_hash": raw_hash, "status": "extracted", "pages": 1, "text_pages": 1}
        summary = {"created_at": "2026-10-17T12:00:00Z", "documents": [row],
                   "page_count": 1, "text_page_count": 1,
                   "pages_sha256": hashlib.sha256(payload).hexdigest()}
        path = folder / "summary.json"
        path.write_text(json.dumps(summary), encoding="utf-8")
        specs.append(spec)
        paths.append(path)
        originals.append(payload)
    missing = {**specs[0], "record_id": "FPT-synthetic-failed",
               "source_url": "https://fixture.example/unavailable.pdf"}
    specs.append(missing)
    first = json.loads(paths[0].read_text())
    first["configured_records_not_registered"] = [missing["record_id"]]
    paths[0].write_text(json.dumps(first), encoding="utf-8")
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"documents": specs, "target_documents": 3}), encoding="utf-8")
    return store, manifest, paths, originals


def test_merge_preserves_page_bytes_and_failed_denominator(tmp_path):
    store, manifest, paths, originals = setup_batches(tmp_path)
    source_bytes = [path.read_bytes() for path in paths]
    output = tmp_path / "merged"
    result_path = merge_snapshots(manifest, paths, store=store, output=output)
    summary = json.loads(result_path.read_text())
    assert (output / "pages.jsonl").read_bytes() == b"".join(originals)
    assert [path.read_bytes() for path in paths] == source_bytes
    assert summary["configured_documents"] == 3
    assert summary["success_documents"] == 2 and summary["failed_documents"] == 1
    assert summary["documents"][-1]["status"] == "not_acquired"
    assert summary["strict_gateway_deliveries"] == 0
    assert summary["network_requests"] == 0
    assert summary["research_prediction_results"] is False
    assert len(summary["input_snapshots"]) == 2


@pytest.mark.parametrize("corruption", ["checksum", "text_hash", "missing_page", "duplicate_page",
                                       "ticker", "wrong_manifest", "overlap", "missing_batch"])
def test_merge_rejects_corrupt_or_ambiguous_batches_before_publishing(tmp_path, corruption):
    store, manifest, paths, _ = setup_batches(tmp_path)
    payload_path = paths[1].parent / "pages.jsonl"
    summary = json.loads(paths[1].read_text())
    page = json.loads(payload_path.read_bytes())
    if corruption == "checksum":
        payload_path.write_bytes(b"changed without new checksum")
    elif corruption in {"text_hash", "missing_page", "duplicate_page"}:
        if corruption == "text_hash":
            page["text"] = "Tampered synthetic text"
        payload = (b"" if corruption == "missing_page" else
                   (json.dumps(page).encode() + b"\n") * (2 if corruption == "duplicate_page" else 1))
        payload_path.write_bytes(payload)
        summary["pages_sha256"] = hashlib.sha256(payload).hexdigest()
        paths[1].write_text(json.dumps(summary), encoding="utf-8")
    elif corruption == "ticker":
        summary["documents"][0]["ticker"] = "HPG"
        paths[1].write_text(json.dumps(summary), encoding="utf-8")
    elif corruption == "wrong_manifest":
        config = json.loads(manifest.read_text())
        config["documents"][1]["title"] = "Changed immutable metadata"
        manifest.write_text(json.dumps(config), encoding="utf-8")
    elif corruption == "overlap":
        paths.append(paths[0])
    else:
        paths.pop()
    output = tmp_path / "rejected"
    with pytest.raises(ValueError):
        merge_snapshots(manifest, paths, store=store, output=output)
    assert not output.exists()


def test_merge_keeps_reviewed_exclusion_instead_of_resurrecting_a_report(tmp_path):
    store, manifest, paths, _ = setup_batches(tmp_path)
    summary = json.loads(paths[1].read_text())
    summary["documents"][0] = {**copy.deepcopy(summary["documents"][0]),
                                "status": "curation_excluded", "error": "Synthetic blank PDF review"}
    summary.update(page_count=0, text_page_count=0, pages_sha256=hashlib.sha256(b"").hexdigest())
    (paths[1].parent / "pages.jsonl").write_bytes(b"")
    paths[1].write_text(json.dumps(summary), encoding="utf-8")
    output = merge_snapshots(manifest, paths, store=store, output=tmp_path / "curated")
    result = json.loads(output.read_text())
    assert result["curation_excluded_documents"] == 1
    assert result["success_documents"] == 1


@pytest.mark.parametrize("selected", [False, True])
@pytest.mark.parametrize("retry_status", ["extracted", "failed"])
def test_retry_requires_explicit_selection_and_preserves_original_failure(tmp_path, selected, retry_status):
    store, manifest, paths, _ = setup_batches(tmp_path)
    if retry_status == "failed":
        failed_retry = json.loads(paths[1].read_text())
        failed_retry["documents"][0].update(status="failed", error="Synthetic second transport failure")
        failed_retry.update(page_count=0, text_page_count=0,
                            pages_sha256=hashlib.sha256(b"").hexdigest())
        (paths[1].parent / "pages.jsonl").write_bytes(b"")
        paths[1].write_text(json.dumps(failed_retry), encoding="utf-8")
    earlier = tmp_path / "earlier-failure"
    earlier.mkdir()
    previous = json.loads(paths[1].read_text())
    record = previous["documents"][0]["record_id"]
    previous["documents"] = [{"record_id": record, "ticker": "FPT", "status": "failed",
                               "error": "Synthetic transport failure"}]
    previous.update(page_count=0, text_page_count=0, pages_sha256=hashlib.sha256(b"").hexdigest())
    (earlier / "pages.jsonl").write_bytes(b"")
    failed_path = earlier / "summary.json"
    failed_path.write_text(json.dumps(previous), encoding="utf-8")
    paths.insert(1, failed_path)
    if not selected:
        with pytest.raises(ValueError, match="explicit failed retry"):
            merge_snapshots(manifest, paths, store=store, output=tmp_path / "rejected")
        return
    path = merge_snapshots(manifest, paths, store=store, output=tmp_path / "recovered",
                           retry_failed_records={record})
    result = json.loads(path.read_text())
    assert result["success_documents"] == (2 if retry_status == "extracted" else 1)
    assert result["explicit_failed_retries"] == [record]
    assert result["earlier_failed_attempts"][0]["earlier_attempt"]["error"] == "Synthetic transport failure"
