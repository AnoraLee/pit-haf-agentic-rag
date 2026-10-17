"""Synthetic offline fixtures only; no real inference or market requests."""

import json
from dataclasses import replace
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from pit_haf.data.evidence import EvidencePage, EvidenceVersion
from pit_haf.data.snapshots import SnapshotStore
from pit_haf.llm.ollama import ModelInspectionError, sha256
from pit_haf.ui.api import create_app
from pit_haf.ui.workspace import Corpus, extract_passage, load_corpus, search_passages


@pytest.fixture
def local_corpus(tmp_path):
    store = SnapshotStore(tmp_path / "data/cache/evidence")
    # Structurally real_document so the production loader is exercised, but all
    # content lives only in pytest's temporary directory and is visibly synthetic.
    digest = store.put_blob(b"synthetic offline fixture; not a real financial report")
    version = EvidenceVersion(
        record_id="FPT-fixture", version_id="fixture-v1", source_id="fixture",
        source_url="https://fixture.example/report.pdf", ticker="FPT",
        document_type="annual_report", title="Synthetic test fixture", content_hash=digest,
        retrieved_at="2026-10-17T10:00:00Z", system_recorded_at="2026-10-17T10:01:00Z",
    )
    store.register(version)
    text = "Dữ liệu giả lập để kiểm thử. Doanh thu đạt 100 tỷ đồng."
    page = EvidencePage(
        record_id=version.record_id, version_id=version.version_id, ticker=version.ticker,
        content_hash=digest, page=1, text=text, text_hash=sha256(text.encode()),
        source_url=version.source_url, retrieved_at=version.retrieved_at,
        extractor="synthetic-test", extraction_status="text_present", data_kind="real_document",
    )
    folder = tmp_path / "outputs/milestone-1/data-pilot/fixture"
    folder.mkdir(parents=True)
    raw = (page.model_dump_json() + "\n").encode()
    (folder / "pages.jsonl").write_bytes(raw)
    (folder / "summary.json").write_text(json.dumps({
        "pages_sha256": sha256(raw), "page_count": 1,
    }))
    return tmp_path, version, page


def test_loader_validates_pages_and_raw_snapshots(local_corpus):
    root, version, _ = local_corpus
    assert len(load_corpus(root).pages) == 1
    store = SnapshotStore(root / "data/cache/evidence")
    store.blob_path(version.content_hash).write_bytes(b"corruption")
    broken = load_corpus(root)
    assert not broken.pages
    assert "checksum" in broken.errors[0].lower()


def test_loader_refuses_changed_page_file(local_corpus):
    root, _, _ = local_corpus
    path = next(root.glob("outputs/milestone-1/data-pilot/*/pages.jsonl"))
    path.write_bytes(path.read_bytes() + b" ")
    assert not load_corpus(root).pages
    assert "Checksum" in load_corpus(root).errors[0]


def test_empty_historical_allowlist_is_not_exploratory(local_corpus):
    root, _, _ = local_corpus
    data = load_corpus(root)
    assert search_passages(data, "doanh thu")
    assert search_passages(data, "doanh thu", allowed_versions=set()) == []
    assert search_passages(data, "doanh thu", ticker="VCB") == []


def test_future_pages_do_not_change_historical_bm25_statistics(local_corpus):
    root, _, page = local_corpus
    original = load_corpus(root)
    future = page.model_copy(update={"version_id": "future-v2", "text": "doanh thu " * 2000})
    expanded = Corpus(original.versions, (*original.pages, future))
    assert search_passages(original, "doanh thu", allowed_versions={page.version_id}) == (
        search_passages(expanded, "doanh thu", allowed_versions={page.version_id})
    )
    hit = search_passages(original, "doanh thu")[0]
    assert page.text[hit.start:hit.end] == hit.text


class FixtureAdapter:
    def __init__(self, quote="Doanh thu đạt 100 tỷ đồng.", *, changed=False, fail=False):
        self.quote, self.changed, self.fail, self.inspections = quote, changed, fail, 0

    def inspect(self, destination):
        self.inspections += 1
        if self.fail:
            raise ModelInspectionError("synthetic offline service failure")
        return {"digest": ("b" if self.changed and self.inspections == 2 else "a") * 64}

    def extract(self, messages, destination):
        sent = json.loads(messages[1]["content"])
        assert "expected_quote" not in sent
        return {"output": {"quote": self.quote, "extracted_numbers": ["100 tỷ đồng"],
                           "summary": "Synthetic fixture summary.", "insufficient_evidence": False},
                "wall_seconds": 0.01}


@pytest.mark.parametrize("quote,changed,expected", [
    ("Doanh thu đạt 100 tỷ đồng.", False, "verified_quote"),
    ("Doanh thu đạt 999 tỷ đồng.", False, "blocked"),
    ("Doanh thu đạt 100 tỷ đồng.", True, "blocked"),
    ("Doanh thu đạt\n100 tỷ đồng.", False, "verified_quote"),
])
def test_extraction_verifies_source_and_model(local_corpus, quote, changed, expected):
    root, _, _ = local_corpus
    data = load_corpus(root)
    hit = search_passages(data, "doanh thu")[0]
    result = extract_passage(data, hit, root / "test-results", mode="exploratory_current",
                             adapter=FixtureAdapter(quote, changed=changed))
    assert result["status"] == expected
    assert result["historical_availability_validated"] is False
    assert result["semantic_support"] == "not_assessed"
    assert json.loads((Path(result["path"]) / "analysis.json").read_text(encoding="utf-8")) == result


def test_service_failure_is_saved_and_passage_tampering_is_rejected(local_corpus):
    root, _, _ = local_corpus
    data = load_corpus(root)
    hit = search_passages(data, "doanh thu")[0]
    result = extract_passage(data, hit, root / "test-results", mode="exploratory_current",
                             adapter=FixtureAdapter(fail=True))
    assert result["status"] == "failed"
    assert "service failure" in result["error"]
    with pytest.raises(ValueError, match="differs"):
        extract_passage(data, replace(hit, text="tampered"), root / "test-results",
                        mode="exploratory_current", adapter=FixtureAdapter())


def test_api_strict_gate_blocks_before_inference(local_corpus, monkeypatch):
    root, _, _ = local_corpus

    def forbidden(*args, **kwargs):
        raise AssertionError("Quarantined documents must not trigger inference")

    monkeypatch.setattr("pit_haf.ui.api.extract_passage", forbidden)
    client = TestClient(create_app(root))
    body = {"query": "doanh thu", "mode": "strict_point_in_time",
            "decision_at": "2025-04-01T16:00:00+07:00"}
    response = client.post("/api/search", json=body)
    assert response.status_code == 200
    assert response.json()["passages"] == []
    assert response.json()["gateway_audit"][0]["status"] == "quarantined"
    assert client.post("/api/analysis", json={**body, "version_id": "fixture-v1", "page": 1,
                                            "start": 0}).status_code == 409
    body["decision_at"] = "2025-04-01T16:00:00"
    assert client.post("/api/search", json=body).status_code == 422


def test_api_returns_sources_and_prevents_cross_origin_inference(local_corpus):
    root, _, _ = local_corpus
    client = TestClient(create_app(root))
    assert client.get("/api/health").json()["interface"] == "react"
    assert client.get("/api/workspace").json()["documents"][0]["pages"] == 1
    assert client.get("/api/documents/fixture-v1/pages/1").json()["text"].startswith("Dữ liệu")
    assert client.get("/api/documents/missing/pages/1").status_code == 404
    assert client.post("/api/search", json={"query": "doanh thu"}).json()["passages"]
    assert client.post("/api/analysis", headers={"Origin": "https://untrusted.example"},
                       json={"query": "doanh thu"}).status_code == 403


def test_api_retrieves_selected_context_and_saves_audit_separately(local_corpus, monkeypatch):
    root, _, _ = local_corpus
    observed = {}

    def extraction(data, hit, destination, **kwargs):
        observed.update(kwargs)
        observed["passage"] = hit
        return {"status": "synthetic-test-only"}

    monkeypatch.setattr("pit_haf.ui.api.extract_passage", extraction)
    client = TestClient(create_app(root))
    search = {"query": "doanh thu", "ticker": "FPT"}
    hit = client.post("/api/search", json=search).json()["passages"][0]
    body = {**search, "version_id": hit["version_id"], "page": hit["page"], "start": hit["start"]}
    assert client.post("/api/analysis", json=body).status_code == 200
    assert observed["retrieval"]["query"] == search["query"]
    assert observed["retrieval"]["ranked_passages"][0]["context_sha256"] == sha256(
        observed["passage"].text.encode()
    )
    assert observed["retrieval"]["gateway_audit_evaluator_only"] == []
    assert client.post("/api/analysis", json={**body, "context": "client tampering"}).status_code == 422
    assert client.post("/api/analysis", json={**body, "start": 9999}).status_code == 409


def test_market_is_only_fetched_on_request_and_preserves_units(local_corpus, monkeypatch):
    import pandas as pd

    root, _, _ = local_corpus
    calls = []

    def market(self, ticker, start, end, **kwargs):
        calls.append((ticker, kwargs))
        frame = pd.DataFrame({"session_date": pd.to_datetime(["2024-01-02", "2024-01-03"]),
                              "close": [100_000, 102_000]})
        frame.attrs = {"adjustment_status": "unknown"}
        return frame

    monkeypatch.setattr("pit_haf.ui.api.VietnamMarketDataProvider.get_prices", market)
    client = TestClient(create_app(root))
    client.get("/api/workspace")
    assert calls == []
    invalid = client.get("/api/market?ticker=FPT&start=2024-07-01&end=2024-01-01")
    assert invalid.status_code == 422 and not calls
    data = client.get("/api/market?ticker=FPT&start=2024-01-01&end=2024-06-30&include_index=true")
    assert data.status_code == 200
    assert data.json()["prices"][-1]["close"] == 102_000
    assert data.json()["historical_availability_validated"] is False
    assert calls == [("FPT", {}), ("VNINDEX", {"asset_type": "index"})]
