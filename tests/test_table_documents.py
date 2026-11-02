"""Document choice must narrow issuer, period and temporal access before PDF reading."""

import json
import sqlite3

import pytest
from fastapi.testclient import TestClient
from test_pdf_text import pdf_catalog as base_pdf_catalog  # noqa: F401
from test_table_evidence import runtime  # noqa: F401

from pit_haf.data.hub import file_sha
from pit_haf.data.pdf_text import search_pdf_text
from pit_haf.data.retrieval_scope import check_document_scope, resolve_scope
from pit_haf.llm.ollama import write_json
from pit_haf.research import table_evidence as runner
from pit_haf.research.table_documents import annual_scope, document_options
from pit_haf.ui.api import create_app


@pytest.fixture
def pdf_catalog(base_pdf_catalog):  # noqa: F811 - shared fixture alias
    return base_pdf_catalog


def test_preview_is_metadata_only_and_does_not_choose_a_document(pdf_catalog, monkeypatch):
    paths = [pdf_catalog.path, pdf_catalog.summary_path]
    before = {p: file_sha(p) for p in paths}
    monkeypatch.setattr(pdf_catalog, "page", lambda *a: pytest.fail("Preview read a page"))
    monkeypatch.setattr(pdf_catalog.store, "read_blob", lambda *a: pytest.fail("Preview read raw PDF"))
    result = document_options(pdf_catalog, query="lợi nhuận 2024", ticker="AAA", profile_id="table_cells_v0.8")
    assert [d["version_id"] for d in result["documents"]] == ["current"]
    assert result["total_pages"] == 1 and result["max_reparsed_pages"] == 400
    assert not result["over_page_budget"] and result["documents"][0]["within_page_budget"]
    assert "version_id" not in result["scope"] and "explicit_caller_choice" in result["selection_basis"]
    assert {p: file_sha(p) for p in paths} == before


def test_explicit_version_reduces_preflight_pages_without_raising_budget(pdf_catalog):
    # A second metadata-only document makes the unselected 426-page scope too large.
    with sqlite3.connect(pdf_catalog.path) as db:
        db.row_factory = sqlite3.Row
        row = dict(db.execute("SELECT * FROM documents WHERE version_id='current'").fetchone())
        db.execute("UPDATE documents SET pages=213 WHERE version_id='current'")
        metadata = json.loads(row["metadata_json"])
        metadata.update(version_id="second", record_id="second")
        row.update(version_id="second", metadata_json=json.dumps(metadata), pages=213)
        db.execute("INSERT INTO documents VALUES (" + ",".join("?" for _ in row) + ")", list(row.values()))
    preview = document_options(pdf_catalog, query="lợi nhuận 2024", ticker="AAA", profile_id="table_cells_v0.8")
    assert preview["total_pages"] == 426 and preview["over_page_budget"]
    assert len(preview["documents"]) == 2 and all(d["within_page_budget"] for d in preview["documents"])
    with pytest.raises(ValueError, match="426 > 400"):
        search_pdf_text(pdf_catalog, "lợi nhuận 2024", scope=annual_scope("lợi nhuận 2024", "AAA"))
    scope = annual_scope("lợi nhuận 2024", "AAA", version_id="current")
    data, hits, trace = search_pdf_text(pdf_catalog, "lợi nhuận 2024", scope=scope)
    assert hits and {v.version_id for v in data.versions} == {"current"}
    assert trace["alternate_text_layer"]["reparsed_pages"] == 1
    assert trace["alternate_text_layer"]["max_reparsed_pages"] == 400


@pytest.mark.parametrize("version", ["other", "past", "future", "absent"])
def test_selected_id_cannot_override_company_or_year_or_invent_a_document(pdf_catalog, monkeypatch, version):
    monkeypatch.setattr(pdf_catalog, "page", lambda *a: pytest.fail("Invalid selection read text"))
    monkeypatch.setattr(pdf_catalog.store, "read_blob", lambda *a: pytest.fail("Invalid selection read PDF"))
    with pytest.raises(ValueError, match="absent or outside"):
        check_document_scope(pdf_catalog, annual_scope("lợi nhuận 2024", "AAA", version_id=version), None)


def test_selected_version_cannot_override_gateway_allowlist(pdf_catalog, monkeypatch):
    monkeypatch.setattr(pdf_catalog, "connect", lambda: pytest.fail("Undelivered selection read metadata"))
    with pytest.raises(ValueError, match="Point-in-Time gateway"):
        check_document_scope(pdf_catalog, annual_scope("lợi nhuận 2024", "AAA", version_id="current"), set())
    preview = document_options(pdf_catalog, query="lợi nhuận 2024", ticker="AAA", profile_id="table_cells_v0.8",
                               mode="strict_point_in_time", decision_at="2025-01-01T00:00:00Z")
    assert not preview["documents"] and preview["total_pages"] == 0


@pytest.mark.parametrize("profile", ["table_cells_v0.7", "table_cells_v0.8", "table_cells_v0.9"])
def test_selected_run_pins_scope_and_replay_rejects_resealed_scope_swap(pdf_catalog, profile):
    root = pdf_catalog.root
    folder, result = runner.run(root, query="lợi nhuận 2024", ticker="AAA", version_id="current", profile_id=profile)
    assert result["scope"]["version_id"] == "current" and result["llm_calls"] == 0
    assert result["source_files"] and runner.replay(root, folder) == result
    result["scope"]["version_id"] = "other"
    write_json(folder / "result.json", result)
    integrity = json.loads((folder / "integrity.json").read_text())
    integrity["files"]["result.json"] = file_sha(folder / "result.json")
    write_json(folder / "integrity.json", integrity)
    with pytest.raises(ValueError, match="selected document scope"):
        runner.replay(root, folder)


def test_no_selection_keeps_legacy_scope_shape_and_rejects_unsafe_ids():
    assert annual_scope("lợi nhuận 2024", "AAA").model_dump() == resolve_scope("lợi nhuận 2024", "AAA").model_dump()
    for value in ("../current", "", "x' OR 1=1", "x" * 129):
        with pytest.raises(ValueError):
            annual_scope("lợi nhuận 2024", "AAA", version_id=value)


def test_document_preview_and_run_api_apply_scope_and_keep_model_opt_in(pdf_catalog, monkeypatch):
    from pit_haf.ui import api as api_module

    # Preview is available without entering the generation runner, even if a caller sends use_model=true.
    original = api_module.run_table_evidence
    monkeypatch.setattr(api_module, "run_table_evidence", lambda *a, **k: pytest.fail("Preview started a run"))
    body = {"ticker": "AAA", "query": "lợi nhuận 2024", "profile_id": "table_cells_v0.8"}
    with TestClient(create_app(pdf_catalog.root)) as client:
        preview = client.post("/api/research/table-evidence/documents", json={**body, "use_model": True})
        assert preview.status_code == 200
        assert [d["version_id"] for d in preview.json()["documents"]] == ["current"]
        assert client.post("/api/research/table-evidence/documents", json=body,
                           headers={"Origin": "https://untrusted.example"}).status_code == 403
        monkeypatch.setattr(api_module, "run_table_evidence", original)
        invalid = client.post("/api/research/table-evidence", json={**body, "document_version_id": "other"})
        assert invalid.status_code == 503 and "outside" in invalid.json()["detail"]
        response = client.post("/api/research/table-evidence", json={**body, "document_version_id": "current"})
        assert response.status_code == 200
        view = response.json()
        assert view["document_selection"]["version_id"] == "current"
        assert view["run"]["llm_calls"] == 0 and view["replay"] == "passed"
        invalid_id = client.post("/api/research/table-evidence", json={**body, "document_version_id": "../current"})
        assert invalid_id.status_code == 422
