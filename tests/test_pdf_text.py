"""Synthetic alternate text fixtures; no real financial facts or human labels."""

import json
import sqlite3

import pytest
from test_table_evidence import runtime, synthetic_pdf  # noqa: F401

from pit_haf.data.catalog import Catalog, build_catalog
from pit_haf.data.evidence import EvidencePage, EvidenceVersion
from pit_haf.data.hub import file_sha
from pit_haf.data.pdf_text import extract_text_pages, search_pdf_text, settings
from pit_haf.data.retrieval_scope import resolve_scope
from pit_haf.data.snapshots import SnapshotStore
from pit_haf.llm.ollama import sha256, write_json
from pit_haf.research import table_evidence as runner


@pytest.fixture
def pdf_catalog(runtime):  # noqa: F811 - shared pytest fixture
    store = SnapshotStore(runtime / "data/cache/evidence")
    digest = store.put_blob(synthetic_pdf(rows=3))
    pages, versions = [], []
    for label, ticker, period in [("current", "AAA", "2024"), ("other", "BBB", "2024"),
                                   ("past", "AAA", "2023"), ("future", "AAA", "2025")]:
        version = EvidenceVersion(record_id=label, version_id=label, source_id="fixture", ticker=ticker,
                                  source_url=f"https://fixture.example/{label}.pdf", document_type="annual_report",
                                  title="Synthetic PDF only", reporting_period=period, content_hash=digest,
                                  retrieved_at="2026-10-29T00:00:00Z", system_recorded_at="2026-10-29T00:00:00Z")
        store.register(version)
        text = "Legacy damaged /uni1EF3 font layer: no useful financial phrase"
        pages.append(EvidencePage(record_id=label, version_id=label, ticker=ticker, content_hash=digest,
                                  page=1, text=text, text_hash=sha256(text.encode()), source_url=version.source_url,
                                  retrieved_at=version.retrieved_at, extractor="synthetic-legacy",
                                  extraction_status="text_present", data_kind="real_document"))
        versions.append({"version_id": label, "record_id": label, "status": "extracted", "pages": 1, "text_pages": 1})
    folder = runtime / "outputs/milestone-1/data-pilot/fixture"
    folder.mkdir(parents=True)
    (folder / "pages.jsonl").write_text("\n".join(p.model_dump_json() for p in pages) + "\n", encoding="utf-8")
    write_json(folder / "summary.json", {"documents": versions, "page_count": len(pages),
                                        "pages_sha256": file_sha(folder / "pages.jsonl")})
    write_json(folder / "catalog.json", build_catalog(folder / "summary.json", store=store,
                                                      output=folder / "catalog.sqlite3"))
    return Catalog(runtime, folder / "summary.json")


def test_alternate_layer_retains_literal_offsets_and_does_not_modify_legacy_catalog(pdf_catalog):
    catalog = pdf_catalog
    paths = [catalog.path, catalog.summary_path, catalog.summary_path.parent / "pages.jsonl"]
    before = {p: file_sha(p) for p in paths}
    data, hits, trace = search_pdf_text(catalog, "lợi nhuận 2024", scope=resolve_scope("lợi nhuận 2024", "AAA"))
    assert hits and {h.version_id for h in hits} == {"current"}
    assert {p.extractor for p in data.pages} == {"pdfplumber_text_v0.7"}
    for hit in hits:
        page = next(p for p in data.pages if p.page == hit.page)
        assert page.text[hit.start:hit.end] == hit.text and page.text_hash == hit.page_text_hash
    assert trace["alternate_text_layer"]["reparsed_pages"] == 1
    assert "/uni1EF3" in catalog.page("current", 1)[1].text
    assert {p: file_sha(p) for p in paths} == before


def test_empty_gateway_never_reads_catalog_text_or_raw_pdf(pdf_catalog, monkeypatch):
    monkeypatch.setattr(pdf_catalog, "connect", lambda: pytest.fail("Empty allowlist touched catalog"))
    monkeypatch.setattr(pdf_catalog.store, "read_blob", lambda *a: pytest.fail("Empty allowlist touched raw PDF"))
    data, hits, trace = search_pdf_text(pdf_catalog, "lợi nhuận 2024", scope=resolve_scope("lợi nhuận 2024", "AAA"),
                                        allowed_versions=set())
    assert not hits and not data.pages and trace["alternate_text_layer"]["reparsed_pages"] == 0


def test_unknown_topic_does_not_mislabel_legacy_fallback_as_alternate_text(pdf_catalog, monkeypatch):
    monkeypatch.setattr(pdf_catalog, "search", lambda *a, **kw: pytest.fail("Legacy fallback must not be relabeled"))
    data, hits, trace = search_pdf_text(pdf_catalog, "thời tiết 2024", scope=resolve_scope("thời tiết 2024", "AAA"))
    assert not data.pages and not hits and trace["stop_reason"] == "unsupported_alternate_text_topic"
    folder, result = runner.run(pdf_catalog.root, query="thời tiết 2024", ticker="AAA", profile_id="table_cells_v0.7")
    assert result["status"] == "abstained_no_table_context" and runner.replay(pdf_catalog.root, folder) == result


def test_metadata_and_allowlist_precede_alternate_pdf_read(pdf_catalog, monkeypatch):
    read = pdf_catalog.page
    seen = []

    def allowed_only(version, page):
        assert version == "current"
        seen.append(version)
        return read(version, page)
    monkeypatch.setattr(pdf_catalog, "page", allowed_only)
    data, hits, trace = search_pdf_text(pdf_catalog, "lợi nhuận", scope=resolve_scope("lợi nhuận", "AAA", reporting_period="all"),
                                        allowed_versions={"current", "other"})
    assert seen and hits and trace["alternate_text_layer"]["reparsed_pages"] == 1
    assert all(v.version_id == "current" for v in data.versions)


def test_over_budget_metadata_stops_before_any_raw_reparse(pdf_catalog, monkeypatch):
    with sqlite3.connect(pdf_catalog.path) as db:
        db.execute("UPDATE documents SET pages=401 WHERE version_id='current'")
    monkeypatch.setattr(pdf_catalog, "page", lambda *a: pytest.fail("Budget preflight must precede raw PDF"))
    with pytest.raises(ValueError, match="metadata page budget"):
        search_pdf_text(pdf_catalog, "lợi nhuận 2024", scope=resolve_scope("lợi nhuận 2024", "AAA"))


@pytest.mark.parametrize("change", ["checksum", "page", "budget"])
def test_raw_text_requires_exact_bytes_and_valid_page_budget(change):
    raw = synthetic_pdf()
    digest = sha256(raw)
    with pytest.raises(ValueError):
        extract_text_pages(raw, "0" * 64 if change == "checksum" else digest,
                           max_pages=0 if change == "budget" else 400,
                           numbers=[0] if change == "page" else None)


def test_image_only_pdf_is_not_invented_or_ocr_processed():
    import io

    from pypdf import PdfWriter

    output = io.BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    writer.write(output)
    raw = output.getvalue()
    assert extract_text_pages(raw, sha256(raw), max_pages=400) == [(1, "")]


@pytest.mark.parametrize("field,value", [("max_reparsed_pages", 999), ("pdfplumber_version", "wrong"), ("ocr_performed", True)])
def test_changed_text_profile_is_rejected(pdf_catalog, field, value):
    path = pdf_catalog.root / "configs/pdf_text_v0_7.json"
    data = json.loads(path.read_text())
    data[field] = value
    write_json(path, data)
    with pytest.raises(ValueError, match="profile"):
        settings(pdf_catalog.root)


def test_new_run_keeps_selected_text_and_replays_from_raw_then_rejects_forgery(pdf_catalog):
    root = pdf_catalog.root
    folder, result = runner.run(root, query="lợi nhuận 2024", ticker="AAA", profile_id="table_cells_v0.7")
    assert result["status"] == "extracted_unreviewed" and result["llm_calls"] == 0
    assert result["context_cells"] == 1 and runner.replay(root, folder) == result
    path = folder / "selected-text-pages.json"
    pages = json.loads(path.read_text(encoding="utf-8"))
    pages[0]["text"] += " forged suffix"
    pages[0]["text_hash"] = sha256(pages[0]["text"].encode())
    write_json(path, pages)
    result["selected_text_pages_sha256"] = file_sha(path)
    write_json(folder / "result.json", result)
    integrity = json.loads((folder / "integrity.json").read_text())
    for name in integrity["files"]:
        integrity["files"][name] = file_sha(folder / name)
    write_json(folder / "integrity.json", integrity)
    with pytest.raises(ValueError, match="differs from raw"):
        runner.replay(root, folder)
