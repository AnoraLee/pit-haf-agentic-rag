"""Synthetic temporary fixtures exercise disk pagination, provenance and historical isolation."""

import hashlib
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from pit_haf.data.catalog import Catalog, build_catalog
from pit_haf.data.evidence import EvidencePage, EvidenceVersion
from pit_haf.data.snapshots import SnapshotError, SnapshotStore
from pit_haf.ui.api import create_app


@pytest.fixture
def disk_fixture(tmp_path):
    store = SnapshotStore(tmp_path / "data/cache/evidence")
    destination = tmp_path / "outputs/milestone-1/data-pilot/synthetic"
    destination.mkdir(parents=True)
    events, lines, versions = [], [], []
    for i in range(3):
        raw = ("Synthetic source fixture " + str(i)).encode()
        digest = store.put_blob(raw)
        mirror = ({"origin": "dataset_mirror", "media_type": "application/json", "dataset_id": "synthetic/news",
                   "dataset_revision": "a" * 40, "dataset_path": "train.csv", "dataset_row_id": str(i),
                   "dataset_split": "train"} if i == 2 else {})
        version = EvidenceVersion(
            record_id=f"synthetic-{i}", version_id=f"synthetic-v{i}", source_id="synthetic",
            source_url=f"https://fixture.example/article/{i}", ticker="FPT" if i != 1 else "HPG",
            related_tickers=("FPT", "HPG") if i == 2 else (),
            title=f"Synthetic fixture title {i}", document_type="news_article" if i == 2 else "annual_report",
            publisher="Synthetic publisher", reporting_period="2024",
            retrieved_at="2026-10-18T00:00:00Z", system_recorded_at="2026-10-18T00:00:01Z",
            content_hash=digest, **mirror)
        store.register(version)
        # Structurally real_document only to exercise production checks, in pytest tmp storage.
        text = ("Doanh thu giả lập đạt 100 tỷ đồng. " * (20 + i)) + f" syntheticunique{i}"
        page = EvidencePage(record_id=version.record_id, version_id=version.version_id,
                            ticker=version.ticker, related_tickers=version.related_tickers,
                            content_hash=digest, page=1, text=text, text_hash=hashlib.sha256(text.encode()).hexdigest(),
                            source_url=version.source_url, retrieved_at=version.retrieved_at,
                            extractor="synthetic-fixture-only", extraction_status="text_present", data_kind="real_document")
        versions.append(version)
        lines.append(page.model_dump_json())
        events.append({"record_id": version.record_id, "version_id": version.version_id, "ticker": version.ticker,
                       "content_hash": digest, "status": "extracted", "pages": 1, "text_pages": 1})
    raw_pages = ("\n".join(lines) + "\n").encode()
    (destination / "pages.jsonl").write_bytes(raw_pages)
    summary_path = destination / "summary.json"
    summary_path.write_text(json.dumps({"documents": events, "page_count": 3,
                                        "pages_sha256": hashlib.sha256(raw_pages).hexdigest()}), encoding="utf-8")
    pointer = build_catalog(summary_path, store=store, output=destination / "catalog.sqlite3")
    (destination / "catalog.json").write_text(json.dumps(pointer), encoding="utf-8")
    return tmp_path, store, versions, Catalog(tmp_path, summary_path)


def test_catalog_pages_filters_counts_and_related_tickers(disk_fixture):
    _, _, _, catalog = disk_fixture
    first = catalog.browse(offset=0, limit=1)
    second = catalog.browse(offset=1, limit=1)
    assert first["total"] == 3 and len(first["documents"]) == 1
    assert first["documents"][0]["version_id"] != second["documents"][0]["version_id"]
    assert catalog.browse(ticker="HPG")["total"] == 2
    assert catalog.browse(origin="dataset_mirror")["total"] == 1
    assert catalog.browse(q="title 2")["total"] == 1
    assert catalog.browse(publisher="' OR 1=1 --")["total"] == 0
    assert catalog.stats()["pdf_documents"] == 2
    assert catalog.stats()["dataset_articles"] == 1
    assert catalog.facets()["origins"] == ["dataset_mirror", "publisher_snapshot"]


def test_catalog_fts_preserves_literal_offsets_and_does_not_read_future_in_strict_subset(disk_fixture):
    _, store, versions, catalog = disk_fixture
    data, hits = catalog.search("doanh thu", ticker="HPG")
    assert hits
    for hit in hits:
        page = next(p for p in data.pages if p.version_id == hit.version_id)
        assert page.text[hit.start:hit.end] == hit.text
    # Future source bytes become corrupt after catalog construction.
    store.blob_path(versions[1].content_hash).write_bytes(b"corrupt future fixture")
    _, past = catalog.search("doanh thu", allowed_versions={versions[0].version_id})
    assert past and all(h.version_id == versions[0].version_id for h in past)
    _, empty = catalog.search("doanh thu", allowed_versions=set())
    assert empty == []
    with pytest.raises(SnapshotError, match="checksum"):
        catalog.search("syntheticunique1")


def test_catalog_api_browses_without_loading_full_corpus_and_handles_missing_page(disk_fixture, monkeypatch):
    root, _, _, _ = disk_fixture
    monkeypatch.setattr("pit_haf.ui.api.load_corpus", lambda *args: pytest.fail("Eager full-corpus load"))
    client = TestClient(create_app(root))
    workspace = client.get("/api/workspace").json()
    assert workspace["document_count"] == 3 and workspace["dataset_article_count"] == 1
    result = client.get("/api/catalog/documents?origin=dataset_mirror&limit=1").json()
    assert result["total"] == 1
    item = result["documents"][0]
    assert client.get(f"/api/documents/{item['version_id']}/pages/1").status_code == 200
    assert client.get("/api/documents/missing/pages/1").status_code == 404
    assert client.get("/api/catalog/documents?limit=1000").status_code == 422
    strict = client.post("/api/search", json={"query": "doanh thu", "mode": "strict_point_in_time",
                                             "decision_at": "2025-01-01T00:00:00Z"}).json()
    assert strict["passages"] == [] and strict["allowed_versions"] == 0


def test_changed_catalog_is_rejected(disk_fixture):
    root, _, _, catalog = disk_fixture
    with catalog.path.open("ab") as stream:
        stream.write(b"changed fixture bytes")
    with pytest.raises(SnapshotError, match="checksum"):
        Catalog(root, catalog.summary_path)


def test_catalog_accepts_workspace_relative_cli_paths(disk_fixture, monkeypatch):
    root, _, _, catalog = disk_fixture
    monkeypatch.chdir(root)
    relative = Catalog(Path("."), catalog.summary_path.relative_to(root))
    assert relative.stats()["documents"] == 3
