"""Coverage is a document/year accounting check, not a claim of financial accuracy."""

import hashlib
import json
from datetime import UTC, datetime

import pytest

from pit_haf.data.coverage import build_release, curate_snapshot
from pit_haf.data.evidence import EvidencePage, EvidenceVersion
from pit_haf.data.snapshots import SnapshotStore


def sample_release(tmp_path):
    store = SnapshotStore(tmp_path / "fixtures")
    documents = []
    for record, period in (("FPT-fixture-vi", "2024"), ("FPT-fixture-en", "2024"),
                           ("FPT-fixture-prior", "2023")):
        digest = store.put_blob(("Synthetic offline fixture: " + record).encode())
        item = EvidenceVersion(
            record_id=record, version_id=record, source_id="fixture",
            source_url=f"https://fixture.example/{record}.pdf", ticker="FPT",
            document_type="annual_report", title="Synthetic coverage fixture", content_hash=digest,
            retrieved_at="2026-10-17T10:00:00Z", system_recorded_at="2026-10-17T10:01:00Z",
            reporting_period=period,
        )
        store.register(item)
        documents.append({"record_id": record, "version_id": record, "ticker": "FPT",
                          "content_hash": digest, "pages": 5, "text_pages": 3,
                          "status": "extracted"})
    documents.append({"record_id": "VCB-fixture-missing", "ticker": "VCB", "status": "failed",
                      "error_type": "OSError", "error": "Synthetic source failure"})
    summary = {"created_at": datetime.now(UTC).isoformat(), "configured_documents": 4,
               "failed_documents": 1, "documents": documents,
               "page_count": 15, "text_page_count": 9, "empty_page_count_no_ocr": 6}
    universe = {"release_id": "synthetic-coverage-only", "target_annual_years": [2023, 2024],
                "issuers": [{"ticker": "FPT", "sector": "Technology"},
                            {"ticker": "VCB", "sector": "Bank"}]}
    return store, summary, universe


def test_translations_do_not_inflate_ticker_years_and_missing_issuers_remain_visible(tmp_path):
    store, summary, universe = sample_release(tmp_path)
    index, coverage = build_release(store, summary, universe)
    assert coverage["acquired_documents"] == 3
    assert coverage["covered_annual_cells"] == 2
    assert coverage["target_annual_cells"] == 4
    assert coverage["observed_issuers"] == 1
    assert coverage["observed_broad_sectors"] == 1
    assert coverage["missing_annual_cells"] == [
        {"ticker": "VCB", "year": 2023, "kind": "annual_report"},
        {"ticker": "VCB", "year": 2024, "kind": "annual_report"},
    ]
    assert coverage["failures"][0]["error_type"] == "OSError"
    assert coverage["strict_eligible_documents"] == 0
    assert index["historical_availability_validated"] is False
    for entry in index["versions"]:
        assert len(entry["registry_metadata_sha256"]) == hashlib.sha256().digest_size * 2


@pytest.mark.parametrize("change", ["duplicate_target", "duplicate_version", "bad_pages", "fixture"])
def test_coverage_rejects_inconsistent_denominators(tmp_path, change):
    store, summary, universe = sample_release(tmp_path)
    if change == "duplicate_target":
        universe["issuers"].append(universe["issuers"][0])
    elif change == "duplicate_version":
        summary["documents"].append(summary["documents"][0])
    elif change == "bad_pages":
        summary["page_count"] = 999
    else:
        summary["documents"][0]["version_id"] = "missing-fixture-version"
    with pytest.raises(ValueError):
        build_release(store, summary, universe)


@pytest.mark.parametrize("wrong_hash", [False, True])
def test_curation_pins_exact_version_keeps_failures_and_does_not_rewrite_text(tmp_path, wrong_hash):
    store, summary, _ = sample_release(tmp_path)
    folder = tmp_path / "before"
    folder.mkdir()
    lines = []
    for version in store.versions():
        for number in range(1, 6):
            text = "Synthetic retained text" if number <= 3 else ""
            page = EvidencePage(
                record_id=version.record_id, version_id=version.version_id, ticker=version.ticker,
                content_hash=version.content_hash, source_url=version.source_url,
                page=number, text=text, text_hash=hashlib.sha256(text.encode()).hexdigest(),
                retrieved_at=version.retrieved_at, extractor="synthetic-fixture", data_kind="real_document",
                extraction_status="text_present" if text else "no_text_ocr_not_performed",
            )
            lines.append((page.version_id, page.model_dump_json().encode()))
    raw = b"\n".join(line for _, line in lines) + b"\n"
    (folder / "pages.jsonl").write_bytes(raw)
    summary.update(pages_sha256=hashlib.sha256(raw).hexdigest(), target_documents=4)
    summary_path = folder / "summary.json"
    summary_path.write_text(json.dumps(summary), encoding="utf-8")
    item = next(v for v in store.versions() if v.record_id == "FPT-fixture-en")
    policy = {"exclude_versions": [{"record_id": item.record_id, "version_id": item.version_id,
                                    "content_hash": "0" * 64 if wrong_hash else item.content_hash,
                                    "reason": "Synthetic review exclusion"}]}
    policy_path = tmp_path / "policy.json"
    policy_path.write_text(json.dumps(policy), encoding="utf-8")
    if wrong_hash:
        with pytest.raises(ValueError, match="exactly one"):
            curate_snapshot(summary_path, tmp_path / "after", policy_path)
        return
    result_path = curate_snapshot(summary_path, tmp_path / "after", policy_path)
    result = json.loads(result_path.read_text(encoding="utf-8"))
    assert result["success_documents"] == 2 and result["failed_documents"] == 2
    assert result["curation_excluded_documents"] == 1
    assert result["page_count"] == 10 and result["text_page_count"] == 6
    assert (tmp_path / "after/pages.jsonl").read_bytes() == (
        b"\n".join(line for version_id, line in lines if version_id != item.version_id) + b"\n"
    )
    assert (folder / "pages.jsonl").read_bytes() == raw
    assert store.read_blob(item.content_hash)
