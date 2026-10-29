"""Synthetic issuer/period/table tests; no real financial answers become gold labels."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from pit_haf.data.catalog import Catalog, build_catalog
from pit_haf.data.evidence import EvidencePage, EvidenceVersion
from pit_haf.data.financial_sections import (
    PROFILE,
    header_years,
    load_profile,
    partition,
    search_financial,
    topic_for,
)
from pit_haf.data.hub import file_sha
from pit_haf.data.retrieval_scope import resolve_scope
from pit_haf.data.snapshots import SnapshotStore
from pit_haf.llm.ollama import sha256, write_json
from pit_haf.research.reports import select_context
from pit_haf.ui.api import create_app


@pytest.fixture
def financial_catalog(tmp_path):
    config = tmp_path / PROFILE
    config.parent.mkdir(parents=True)
    config.write_bytes((Path(__file__).resolve().parents[1] / PROFILE).read_bytes())
    store = SnapshotStore(tmp_path / "data/cache/evidence")
    version_rows, pages = [], []
    statement = ("BÁO CÁO KẾT QUẢ HOẠT ĐỘNG HỢP NHẤT\n"
                 "STT Chỉ tiêu Thuyết minh 2024\nTriệu VND\n2023\nTriệu VND\n"
                 "Lợi nhuận trước thuế 1.000 900\nLỢI NHUẬN SAU THUẾ 800 700\n")
    comparison = ("Số liệu so sánh - BÁO CÁO KẾT QUẢ HOẠT ĐỘNG HỢP NHẤT\n"
                  "31/12/2023\nTriệu VND\nLợi nhuận trước thuế 900 890\nLợi nhuận sau thuế 700 690\n"
                  "Ngày phê duyệt báo cáo: 28 tháng 3 năm 2025\n")
    for label, ticker, period, texts in [
        ("current", "AAA", "2024", [statement, comparison, "Chính sách kế toán\nNguyên tắc ghi nhận doanh thu\n"]),
        ("old", "AAA", "2023", [statement.replace("2024", "2023")]),
        ("other", "BBB", "2024", [statement]),
        ("future", "AAA", "2025", [statement.replace("2024", "2025")]),
    ]:
        digest = store.put_blob(("Synthetic PDF " + label).encode())
        version = EvidenceVersion(record_id=label, version_id=label, source_id="fixture",
                                  source_url=f"https://fixture.example/{label}.pdf", ticker=ticker,
                                  document_type="annual_report", title="Synthetic issuer statement",
                                  reporting_period=period, content_hash=digest,
                                  retrieved_at="2026-10-23T00:00:00Z", system_recorded_at="2026-10-23T00:00:00Z")
        store.register(version)
        version_rows.append({"version_id": label, "record_id": label, "status": "extracted",
                             "pages": len(texts), "text_pages": len(texts)})
        for number, text in enumerate(texts, 1):
            pages.append(EvidencePage(record_id=label, version_id=label, ticker=ticker,
                                      content_hash=digest, page=number, text=text, text_hash=sha256(text.encode()),
                                      source_url=version.source_url, retrieved_at=version.retrieved_at,
                                      extractor="synthetic-only", extraction_status="text_present", data_kind="real_document"))
    folder = tmp_path / "outputs/milestone-1/data-pilot/synthetic"
    folder.mkdir(parents=True)
    (folder / "pages.jsonl").write_bytes(("\n".join(p.model_dump_json() for p in pages) + "\n").encode())
    write_json(folder / "summary.json", {"documents": version_rows, "page_count": len(pages),
                                        "pages_sha256": file_sha(folder / "pages.jsonl")})
    pointer = build_catalog(folder / "summary.json", store=store, output=folder / "catalog.sqlite3")
    write_json(folder / "catalog.json", pointer)
    return Catalog(tmp_path, folder / "summary.json")


def test_header_years_include_current_year_embedded_in_label_and_exclude_footer_dates():
    text = ("STT Chỉ tiêu Thuyết minh 2024\nTriệu VND\n2023\nTriệu VND\n"
            "Lợi nhuận 1.000 900\nNgười lập: kế toán\nNgày 28 tháng 3 năm 2025\n")
    assert header_years(text) == {"2023", "2024"}
    comparison = ("Các sự kiện sau ngày 31 tháng 12 năm 2024\n"
                  "31/12/2023\nTriệu VND\nLợi nhuận 900 890\n")
    assert header_years(comparison) == {"2023"}
    assert header_years("2022Chỉ tiêu (Đơn vị: Tỷ đồng) 2023 2024BÁO CÁO\n") == {"2022", "2023", "2024"}


def test_section_search_excludes_other_issuer_period_and_restatement_only_page(financial_catalog):
    catalog = financial_catalog
    scope = resolve_scope("lợi nhuận năm 2024", "AAA")
    data, hits, trace = search_financial(catalog, "lợi nhuận năm 2024", scope=scope)
    assert hits and {(h.version_id, h.page) for h in hits} == {("current", 1)}
    assert trace["pages_scored"] == 3 and trace["topic"] == "income"
    selected = select_context(data, hits, "AAA", mode="exploratory_current", scope=scope)
    assert sum(len(s["passage"]["text"]) for s in selected) <= 2100
    for h in hits:
        original = next(p for p in data.pages if (p.version_id, p.page) == (h.version_id, h.page))
        assert h.text == original.text[h.start:h.end] and len(h.text) <= 700


def test_gateway_allowlist_precedes_page_reads_and_statistics(financial_catalog, monkeypatch):
    catalog = financial_catalog
    scope = resolve_scope("lợi nhuận", "AAA", reporting_period="all")
    read = catalog.page
    observed = []
    def page(version, number):
        observed.append(version)
        assert version == "current"
        return read(version, number)
    monkeypatch.setattr(catalog, "page", page)
    data, hits, trace = search_financial(catalog, "lợi nhuận", scope=scope, allowed_versions={"current"})
    assert observed and hits and trace["pages_scored"] == 3
    assert all(v.version_id == "current" for v in data.versions)
    monkeypatch.setattr(catalog, "connect", lambda: pytest.fail("Empty gateway must not read catalog text"))
    empty, hits, trace = search_financial(catalog, "lợi nhuận", scope=scope, allowed_versions=set())
    assert not hits and not empty.pages and trace["stop_reason"] == "empty_gateway_allowlist"


def test_empty_scope_never_falls_back_to_other_period(financial_catalog):
    scope = resolve_scope("lợi nhuận", "AAA", reporting_period="2022")
    data, hits, trace = search_financial(financial_catalog, "lợi nhuận", scope=scope)
    assert not data.pages and not hits and trace["pages_scored"] == 0
    assert trace["stop_reason"] == "no_matching_financial_section"


def test_unknown_topic_fallback_retains_allowlist_and_scope(financial_catalog, monkeypatch):
    scope = resolve_scope("thời tiết", "AAA", reporting_period="2024")
    def search(query, **kwargs):
        assert kwargs == {"ticker": "AAA", "scope": scope, "allowed_versions": {"current"}}
        return "fixture-data", []
    monkeypatch.setattr(financial_catalog, "search", search)
    data, hits, trace = search_financial(financial_catalog, "thời tiết", scope=scope, allowed_versions={"current"})
    assert data == "fixture-data" and not hits and trace["fallback_reason"]


def test_profile_and_partition_preserve_budget_and_literal_bytes(financial_catalog):
    profile = load_profile(financial_catalog.root)
    assert topic_for("Kế hoạch doanh thu năm 2027", profile) == "outlook"
    text = ("Giá trị 123.456.789 tỷ đồng.\n" * 200) + "Kết thúc"
    spans = list(partition(text))
    assert "".join(text[a:b] for a, b in spans) == text
    assert all(0 < b - a <= 700 for a, b in spans)
    profile["max_passages"] = 99
    write_json(financial_catalog.root / PROFILE, profile)
    with pytest.raises(ValueError, match="budget"):
        load_profile(financial_catalog.root)


def test_corrupt_selected_pdf_is_not_replaced_with_another_source(financial_catalog):
    catalog = financial_catalog
    version = catalog.page("current", 1)[0]
    catalog.store.blob_path(version.content_hash).write_bytes(b"corrupted")
    with pytest.raises(ValueError, match="checksum"):
        search_financial(catalog, "lợi nhuận", scope=resolve_scope("lợi nhuận", "AAA", reporting_period="2024"))


def test_report_api_selects_section_profile_and_preserves_strict_empty_cohort(financial_catalog, monkeypatch):
    observed = {}
    def runner(root, data, hits, **kwargs):
        observed.update(kwargs)
        observed["hits"] = hits
        return {"status": "synthetic-only"}
    monkeypatch.setattr("pit_haf.ui.api.run_report", runner)
    client = TestClient(create_app(financial_catalog.root))
    request = {"ticker": "AAA", "query": "lợi nhuận năm 2024", "retrieval_profile": "financial_sections_v0.3"}
    assert client.post("/api/research/report", json=request).status_code == 200
    assert {(h.version_id, h.page) for h in observed["hits"]} == {("current", 1)}
    assert observed["retrieval_trace"]["topic"] == "income"
    assert client.post("/api/research/report", json={**request, "retrieval_profile": "lexical_v0.2"}).status_code == 200
    assert observed["retrieval_trace"] is None
    strict = {**request, "mode": "strict_point_in_time", "decision_at": "2025-01-01T00:00:00+07:00"}
    assert client.post("/api/research/report", json=strict).status_code == 200
    assert not observed["hits"]
    assert observed["retrieval_trace"]["stop_reason"] == "empty_gateway_allowlist"
    assert client.post("/api/research/report", json={**request, "retrieval_profile": "unknown"}).status_code == 422
