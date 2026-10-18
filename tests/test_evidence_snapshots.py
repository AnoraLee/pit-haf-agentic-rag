import hashlib
import io
import json
import sqlite3
from datetime import UTC, date, datetime

import pytest
from pydantic import ValidationError

from pit_haf.data.evidence import EvidenceVersion, date_upper_bound, version_id_for
from pit_haf.data.gateway import deliver_as_of as production_deliver_as_of
from pit_haf.data.pilot import acquire_pilot, approved_url, extract_pdf_pages
from pit_haf.data.point_in_time import PointInTimeError
from pit_haf.data.snapshots import SnapshotError, SnapshotStore


@pytest.fixture
def store(tmp_path):
    return SnapshotStore(tmp_path / "store")


def deliver_as_of(store, **kwargs):
    return production_deliver_as_of(store, expected_data_kind="test_fixture", **kwargs)


def evidence(store, payload=b"original", **changes):
    content_hash = store.put_blob(payload)
    proof_hash = store.put_blob(b"test fixture: manually verified time and version proof")
    values = {
        "record_id": "FPT-report", "version_id": version_id_for("FPT-report", content_hash),
        "source_id": "official-fixture", "source_url": "https://official.example/report.pdf",
        "ticker": "FPT", "document_type": "financial_statement", "title": "Fixture report",
        "content_hash": content_hash, "retrieved_at": "2026-10-17T10:00:00+07:00",
        "system_recorded_at": "2026-10-17T10:01:00+07:00", "data_kind": "test_fixture",
        "available_at": "2024-01-02T09:00:00+07:00",
        "published_at": "2024-01-02T09:00:00+07:00",
        "availability_basis": "verified_publication", "timestamp_precision": "minute",
        "timestamp_evidence_hash": proof_hash,
        "version_basis": "archived_bytes", "version_evidence_hash": proof_hash,
        "proof_reviewed_by": "offline-test-fixture",
        "proof_review_note": "Fixture time/version assertion; not real market proof.",
    }
    values.update(changes)
    return EvidenceVersion(**values)


def test_snapshot_identity_and_append_only_registry(store):
    item = evidence(store)
    store.register(item)
    store.register(item)
    assert store.versions() == (item,)
    assert store.read_blob(item.content_hash) == b"original"
    with sqlite3.connect(store.database) as db:
        with pytest.raises(sqlite3.IntegrityError, match="immutable"):
            db.execute("DELETE FROM versions")
    store.log_acquisition({"kind": "test_fixture", "status": "failed"})
    with sqlite3.connect(store.database) as db:
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            db.execute("UPDATE acquisitions SET event_json = '{}' ")


def test_production_gateway_never_delivers_annotated_test_fixtures(store):
    store.register(evidence(store))
    result = production_deliver_as_of(store, decision_at="2024-01-03T00:00:00Z")
    assert not result.deliveries
    assert result.audit[0]["reasons"] == ["unexpected_data_kind"]


def test_duplicate_version_cannot_change_timestamp_or_content(store):
    original = evidence(store)
    store.register(original)
    changed = evidence(store, available_at="2024-01-03T09:00:00+07:00")
    with pytest.raises(SnapshotError, match="immutable metadata"):
        store.register(changed)
    another = evidence(store, payload=b"changed", version_id=original.version_id)
    with pytest.raises(SnapshotError, match="immutable metadata"):
        store.register(another)


def test_same_record_content_cannot_have_two_version_ids(store):
    store.register(evidence(store))
    with pytest.raises(SnapshotError, match="different immutable version ID"):
        store.register(evidence(store, version_id="different"))


def test_record_cannot_switch_source_or_supersede_another_record(store):
    original = evidence(store)
    store.register(original)
    with pytest.raises(SnapshotError, match="change source_id"):
        store.register(evidence(store, payload=b"new", source_id="other"))
    with pytest.raises(SnapshotError, match="same logical record"):
        store.register(evidence(store, payload=b"new", supersedes_version_id="missing"))


def test_snapshot_detects_corruption_and_refuses_overwrite(store):
    item = evidence(store)
    store.blob_path(item.content_hash).write_bytes(b"tampered")
    with pytest.raises(SnapshotError, match="checksum mismatch"):
        store.read_blob(item.content_hash)
    with pytest.raises(SnapshotError, match="checksum mismatch"):
        store.put_blob(b"original")
    with pytest.raises(SnapshotError, match="checksum mismatch"):
        store.register(item)


def test_registry_checks_metadata_checksum(store):
    store.register(evidence(store))
    with sqlite3.connect(store.database) as db:
        db.execute("DROP TRIGGER immutable_versions_update")
        db.execute("UPDATE versions SET metadata_json = '{}' ")
    with pytest.raises(SnapshotError, match="metadata checksum"):
        store.versions()


@pytest.mark.parametrize("field", ["retrieved_at", "system_recorded_at", "available_at", "published_at"])
def test_naive_timestamps_are_rejected(store, field):
    with pytest.raises(ValidationError, match="explicit timezone"):
        evidence(store, **{field: datetime(2024, 1, 2, 9)})


def test_cannot_substitute_retrieval_for_unverified_availability(store):
    with pytest.raises(ValidationError, match="Unverified evidence"):
        evidence(store, availability_basis="unverified")
    item = evidence(store, availability_basis="unverified", available_at=None,
                    published_at=None, timestamp_precision="unknown")
    store.register(item)
    result = deliver_as_of(store, decision_at="2026-10-18T00:00:00+07:00")
    assert not result.deliveries
    assert "availability_unverified" in result.audit[0]["reasons"]


def test_missing_historical_revision_proof_is_quarantined(store):
    item = evidence(store, version_basis="observation_only", version_evidence_hash=None)
    store.register(item)
    result = deliver_as_of(store, decision_at="2024-01-03T00:00:00+07:00")
    assert not result.deliveries
    assert "historical_revision_proof_missing" in result.audit[0]["reasons"]


def test_missing_timestamp_proof_is_quarantined(store):
    store.register(evidence(store, timestamp_evidence_hash=None))
    result = deliver_as_of(store, decision_at="2024-01-03T00:00:00+07:00")
    assert not result.deliveries
    assert "timestamp_proof_missing" in result.audit[0]["reasons"]


def test_time_and_revision_hash_presence_is_not_a_proof_review(store):
    store.register(evidence(store, proof_reviewed_by=None, proof_review_note=None))
    result = deliver_as_of(store, decision_at="2024-01-03T00:00:00+07:00")
    assert not result.deliveries
    assert "time_and_version_proof_review_missing" in result.audit[0]["reasons"]


def test_date_only_is_separate_sensitivity_cohort_and_upper_bound(store):
    bound = date_upper_bound(date(2024, 1, 2))
    assert bound.isoformat() == "2024-01-03T00:00:00+07:00"
    item = evidence(store, available_at=bound, published_at=None, publication_date="2024-01-02",
                    availability_basis="conservative_date_bound", timestamp_precision="day")
    store.register(item)
    strict = deliver_as_of(store, decision_at="2024-01-03T00:00:00+07:00")
    assert not strict.deliveries
    assert "date_only_excluded_from_strict" in strict.audit[0]["reasons"]
    before = deliver_as_of(store, decision_at="2024-01-02T23:59:59+07:00", cohort="conservative")
    assert not before.deliveries
    allowed = deliver_as_of(store, decision_at=bound.isoformat(), cohort="conservative")
    assert len(allowed.deliveries) == 1
    assert allowed.deliveries[0].evidence.published_at is None
    with pytest.raises(ValidationError, match="next local midnight"):
        evidence(store, available_at="2024-01-02T12:00:00+07:00", published_at=None,
                 publication_date="2024-01-02", availability_basis="conservative_date_bound",
                 timestamp_precision="day")


def test_late_revision_delivers_original_then_revision_without_future_bytes(store):
    original = evidence(store)
    store.register(original)
    revised = evidence(store, payload=b"revised value 120", available_at="2024-01-04T09:00:00+07:00",
                       published_at="2024-01-04T09:00:00+07:00",
                       supersedes_version_id=original.version_id)
    store.register(revised)
    early = deliver_as_of(store, decision_at="2024-01-02T16:00:00+07:00")
    late = deliver_as_of(store, decision_at="2024-01-04T16:00:00+07:00")
    assert [item.raw_bytes for item in early.deliveries] == [b"original"]
    assert [item.raw_bytes for item in late.deliveries] == [b"revised value 120"]
    assert any(row["version_id"] == revised.version_id and row["status"] == "future"
               for row in early.audit)


def test_future_injection_does_not_change_delivered_context_or_open_future_blob(store):
    store.register(evidence(store))
    before = deliver_as_of(store, decision_at="2024-01-02T16:00:00+07:00")
    future = evidence(store, payload=b"future secret", record_id="future-other",
                      version_id="future-version", available_at="2025-01-01T00:00:00Z")
    store.register(future)
    store.blob_path(future.content_hash).write_bytes(b"corrupted future should not be opened")
    after = deliver_as_of(store, decision_at="2024-01-02T16:00:00+07:00")
    assert before.deliveries == after.deliveries
    assert b"future secret" not in b"".join(item.raw_bytes for item in after.deliveries)


def test_corrupt_latest_does_not_silently_fallback_to_older_revision(store):
    original = evidence(store)
    store.register(original)
    revised = evidence(store, payload=b"revised", available_at="2024-01-04T09:00:00+07:00")
    store.register(revised)
    store.blob_path(revised.content_hash).write_bytes(b"damaged")
    result = deliver_as_of(store, decision_at="2024-01-05T00:00:00+07:00")
    assert not result.deliveries
    statuses = {row["version_id"]: row["status"] for row in result.audit}
    assert statuses == {original.version_id: "superseded", revised.version_id: "quarantined"}


@pytest.mark.parametrize("missing", [
    {"timestamp_evidence_hash": None},
    {"version_basis": "observation_only", "version_evidence_hash": None},
    {"proof_reviewed_by": None, "proof_review_note": None},
])
def test_known_new_revision_missing_proof_never_falls_back_to_old(store, missing):
    original = evidence(store)
    store.register(original)
    revised = evidence(store, payload=b"known revised content", available_at="2024-01-04T09:00:00Z",
                       supersedes_version_id=original.version_id, **missing)
    store.register(revised)
    before = deliver_as_of(store, decision_at="2024-01-03T00:00:00Z")
    assert [entry.raw_bytes for entry in before.deliveries] == [b"original"]
    after = deliver_as_of(store, decision_at="2024-01-05T00:00:00Z")
    assert not after.deliveries
    statuses = {row["version_id"]: row["status"] for row in after.audit}
    assert statuses == {original.version_id: "superseded", revised.version_id: "quarantined"}


def test_ambiguous_revision_timestamp_rejects_entire_batch(store):
    store.register(evidence(store))
    store.register(evidence(store, payload=b"ambiguous different revision"))
    with pytest.raises(PointInTimeError, match="share a record_id"):
        deliver_as_of(store, decision_at="2024-01-03T00:00:00+07:00")


@pytest.mark.parametrize("digest", ["../private", "Z" * 64, "a" * 63])
def test_blob_paths_cannot_escape_content_store(store, digest):
    with pytest.raises(SnapshotError, match="SHA-256"):
        store.blob_path(digest)


@pytest.mark.parametrize("url", [
    "http://official.example/report.pdf", "https://127.0.0.1/private",
    "https://official.example.evil.test/file", "https://u:p@official.example/report.pdf",
    "https://official.example:8080/file",
])
def test_public_acquisition_rejects_out_of_scope_urls(url):
    with pytest.raises(ValueError, match="allowlist"):
        approved_url(url, {"official.example"})


def blank_pdf():
    from pypdf import PdfWriter

    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    stream = io.BytesIO()
    writer.write(stream)
    return stream.getvalue()


def test_pdf_extraction_preserves_page_locator_and_marks_no_ocr(store):
    item = evidence(store, payload=blank_pdf())
    pages = extract_pdf_pages(store, item)
    assert len(pages) == 1
    page = pages[0]
    assert page.page == 1 and page.record_id == item.record_id and page.version_id == item.version_id
    assert page.content_hash == item.content_hash
    assert page.text == "" and page.text_hash == hashlib.sha256(b"").hexdigest()
    assert page.extraction_status == "no_text_ocr_not_performed"
    assert page.extractor.endswith(";no_ocr")


def test_parser_content_skip_is_retained_as_page_diagnostic(store, monkeypatch):
    import logging

    import pypdf

    class PartialPage:
        def extract_text(self):
            logging.getLogger("pypdf.test_fixture").warning(
                "Exceeded fixture form limit; further form content is skipped."
            )
            return "Only the synthetic retained text."

    class Reader:
        is_encrypted = False
        pages = [PartialPage()]

        def __init__(self, *args, **kwargs):
            pass

    monkeypatch.setattr(pypdf, "PdfReader", Reader)
    diagnostics = {}
    pages = extract_pdf_pages(store, evidence(store, payload=blank_pdf()), diagnostics)
    assert pages[0].text == "Only the synthetic retained text."
    assert pages[0].extraction_status == "text_present"
    assert diagnostics["parser_warning_count"] == 1
    assert diagnostics["potentially_partial_text_pages"] == [1]
    assert "skipped" in diagnostics["parser_warnings"][0]["message"]


def test_pilot_records_acquisition_failure_and_true_shortfall(store, tmp_path, monkeypatch):
    from pit_haf.data import pilot

    def fetch(url, hosts):
        if url.endswith("fail.pdf"):
            raise OSError("test fixture unavailable")
        raw = blank_pdf() if url.endswith("ok.pdf") else b"User-agent: *\nAllow: /\n"
        return raw, {"source_url": url, "http_status": 200, "headers": {},
                     "retrieved_at": datetime.now(UTC).isoformat()}

    monkeypatch.setattr(pilot, "fetch_public", fetch)
    manifest = {
        "allowed_hosts": ["official.example"], "sources": [], "target_documents": 24,
        "documents": [
            {"record_id": key, "source_id": "official-fixture", "ticker": "FPT",
             "source_url": f"https://official.example/{key}.pdf", "document_type": "report",
             "title": "Test fixture", "data_kind": "test_fixture"}
            for key in ("ok", "fail")
        ],
    }
    result = acquire_pilot(manifest, store=store, output=tmp_path / "pilot", delay=0)
    assert result["run_kind"] == "test_fixture"
    assert result["success_documents"] == 1 and result["failed_documents"] == 1
    assert result["target_shortfall"] == 23 and result["strict_gateway_deliveries"] == 0
    assert result["empty_page_count_no_ocr"] == 1
    pages = [json.loads(line) for line in (tmp_path / "pilot/pages.jsonl").read_text().splitlines()]
    assert len(pages) == 1 and pages[0]["data_kind"] == "test_fixture"
    item = store.versions()[0]
    assert item.available_at is None and item.published_at is None


@pytest.mark.parametrize("changed", [
    {"source_id": "changed-publisher"}, {"ticker": "HPG"}, {"data_kind": "real_document"},
])
def test_repeated_acquisition_cannot_relabel_immutable_metadata(store, tmp_path, monkeypatch, changed):
    from pit_haf.data import pilot

    payload = blank_pdf()

    def fetch(url, hosts):
        return (payload if url.endswith("ok.pdf") else b"User-agent: *\nAllow: /\n"), {
            "source_url": url, "http_status": 200, "headers": {},
            "retrieved_at": datetime.now(UTC).isoformat(),
        }

    monkeypatch.setattr(pilot, "fetch_public", fetch)
    spec = {"record_id": "ok", "source_id": "official-fixture", "ticker": "FPT",
            "source_url": "https://official.example/ok.pdf", "document_type": "report",
            "title": "Test fixture", "data_kind": "test_fixture"}
    config = {"allowed_hosts": ["official.example"], "sources": [], "documents": [spec]}
    first = acquire_pilot(config, store=store, output=tmp_path / "first", delay=0)
    assert first["success_documents"] == 1
    first_retrieval = store.versions()[0].retrieved_at
    repeated = acquire_pilot(config, store=store, output=tmp_path / "repeat", delay=0)
    assert repeated["success_documents"] == 1
    assert store.versions()[0].retrieved_at == first_retrieval
    config["documents"] = [{**spec, **changed}]
    conflict = acquire_pilot(config, store=store, output=tmp_path / "conflict", delay=0)
    assert conflict["success_documents"] == 0 and conflict["failed_documents"] == 1
    assert "immutable version metadata" in conflict["documents"][0]["error"]
    assert not (tmp_path / "conflict/pages.jsonl").read_bytes()


def test_snapshot_locator_is_derived_and_cannot_escape_store(store):
    item = evidence(store, event_at="2023-12-31")
    assert item.raw_snapshot_path == f"blobs/{item.content_hash[:2]}/{item.content_hash}"
    assert item.event_at == date(2023, 12, 31)
    assert item.adjustment_status == "not_applicable"
    with pytest.raises(ValidationError, match="content-addressed"):
        evidence(store, raw_snapshot_path="../../outside.pdf")


def test_expansion_can_reuse_local_snapshot_without_redownloading(store, tmp_path, monkeypatch):
    from pit_haf.data import pilot

    item = evidence(store, payload=blank_pdf())
    store.register(item)
    requests = []

    def fetch(url, hosts):
        requests.append(url)
        assert not url.endswith(".pdf"), "Local reuse must not re-download the PDF"
        return b"User-agent: *\nAllow: /\n", {"source_url": url, "http_status": 200,
                                               "retrieved_at": datetime.now(UTC).isoformat()}

    monkeypatch.setattr(pilot, "fetch_public", fetch)
    spec = {key: getattr(item, key) for key in (
        "record_id", "source_id", "source_url", "ticker", "document_type", "title", "data_kind"
    )}
    config = {"allowed_hosts": ["official.example"], "sources": [], "documents": [spec]}
    result = acquire_pilot(config, store=store, output=tmp_path / "reuse", delay=0,
                           skip_registered=True)
    assert result["success_documents"] == 1
    assert result["skip_registered_without_remote_revalidation"] is True
    assert result["documents"][0]["registration"] == "local_reuse_without_remote_revalidation"
    assert store.versions()[0].retrieved_at == item.retrieved_at
    assert requests == ["https://official.example/robots.txt"]
    assert (tmp_path / "reuse/summary.json").is_file()
    assert not (tmp_path / "reuse/summary.json.tmp").exists()


def test_local_reuse_rejects_ambiguous_versions(store, tmp_path, monkeypatch):
    from pit_haf.data import pilot

    original = evidence(store, payload=blank_pdf())
    store.register(original)
    store.register(evidence(store, payload=b"second synthetic revision",
                            available_at="2024-01-04T09:00:00Z"))
    monkeypatch.setattr(pilot, "fetch_public", lambda *args: (
        b"User-agent: *\nAllow: /\n", {"retrieved_at": datetime.now(UTC).isoformat()}
    ))
    spec = {key: getattr(original, key) for key in (
        "record_id", "source_id", "source_url", "ticker", "document_type", "title", "data_kind"
    )}
    result = acquire_pilot({"allowed_hosts": ["official.example"], "sources": [],
                            "documents": [spec]}, store=store, output=tmp_path / "ambiguous",
                           delay=0, skip_registered=True)
    assert result["success_documents"] == 0 and result["failed_documents"] == 1
    assert "exactly one version" in result["documents"][0]["error"]


@pytest.mark.parametrize("status,headers,body,accepted", [
    (200, {"Content-Length": "3"}, b"abc", True),
    (200, {}, b"abc", True),
    (206, {"Content-Range": "bytes 0-2/100"}, b"abc", False),
    (200, {"Content-Range": "bytes 0-2/100"}, b"abc", False),
    (200, {"Content-Length": "5"}, b"abc", False),
])
def test_fetch_rejects_incomplete_responses(monkeypatch, status, headers, body, accepted):
    from pit_haf.data import pilot

    class Response(io.BytesIO):
        url = "https://fixture.example/document.pdf"

    response = Response(body)
    response.status, response.headers = status, headers

    class Opener:
        def open(self, *args, **kwargs):
            assert args[0].full_url == "https://fixture.example/document%20with%20space.pdf"
            return response

    monkeypatch.setattr(pilot.urllib.request, "build_opener", lambda *args: Opener())
    if accepted:
        raw, metadata = pilot.fetch_public("https://fixture.example/document with space.pdf",
                                           {"fixture.example"})
        assert raw == body and metadata["http_status"] == 200
    else:
        with pytest.raises(ValueError):
            pilot.fetch_public("https://fixture.example/document with space.pdf", {"fixture.example"})


@pytest.mark.parametrize("limit", [0, True, 128 * 1024 * 1024 + 1])
def test_fetch_cannot_disable_or_exceed_the_hard_response_bound(limit):
    from pit_haf.data.pilot import fetch_public

    with pytest.raises(ValueError, match="128 MiB"):
        fetch_public("https://fixture.example/file.pdf", {"fixture.example"}, max_bytes=limit)


@pytest.mark.parametrize("value", [1704189600, "2024-01-02T09:00:00.000000001+07:00"])
def test_evidence_timestamps_cannot_silently_coerce_epoch_or_lose_precision(store, value):
    with pytest.raises(ValidationError):
        evidence(store, available_at=value)


def test_event_time_requires_timezone_when_more_precise_than_a_date(store):
    with pytest.raises(ValidationError, match="timezone"):
        evidence(store, event_at="2023-12-31T12:00:00")
