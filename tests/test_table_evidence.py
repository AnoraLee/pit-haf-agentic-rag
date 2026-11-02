"""Synthetic PDF geometry, abstention and raw replay tests; no financial gold labels."""

import copy
import io
import json
from pathlib import Path

import pytest
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from pit_haf.data.evidence import EvidencePage, EvidenceVersion
from pit_haf.data.pdf_tables import bind_words, extract_page, replay_page
from pit_haf.data.snapshots import SnapshotStore
from pit_haf.llm.ollama import HttpReply, OllamaAdapter, OllamaConfig, sha256
from pit_haf.research import table_evidence as runner
from pit_haf.ui.workspace import Corpus, Passage


def words(rows):
    result = []
    for top, parts in rows:
        for text, x0, x1 in parts:
            result.append({"id": len(result), "text": text, "x0": x0, "x1": x1,
                           "top": top, "bottom": top + 10})
    return result


def table_words(unit=True):
    return words([
        (20, [("Hop", 40, 60), ("nhat", 62, 85)]),
        *(([(40, [("Trieu", 40, 65), ("VND", 67, 90)])]) if unit else []),
        (60, [("STT", 40, 55), ("Chi", 60, 70), ("tieu", 72, 90),
              ("2024", 280, 300), ("2023", 380, 400)]),
        (90, [("1", 40, 45), ("Loi", 60, 80), ("nhuan", 82, 112), ("(12)", 280, 300), ("25", 380, 400)]),
        (120, [("2", 40, 45), ("Tien", 60, 80), ("99", 280, 300), ("13", 380, 400)]),
    ])


def bind(ws):
    return bind_words(ws, width=600, height=800, content_hash="a" * 64, page_number=1)


def test_geometry_binds_year_row_and_parenthesized_sign_without_rewriting():
    b = bind(table_words())
    assert len(b["cells"]) == 4
    profit = next(c for c in b["cells"] if c["year"] == "2024" and c["fields"]["label"]["text"] == "Loi nhuan")
    f = profit["fields"]
    assert f["value"]["text"] == "(12)" and f["unit"]["value"] == "triệu VND"
    assert f["statement_scope"]["value"] == "consolidated"
    assert profit["structural_status"] == "linked_candidate" and not profit["human_reviewed"]
    assert profit["semantic_support"] == "not_assessed"
    assert f["label"]["word_ids"] != f["value"]["word_ids"]


def test_missing_unit_remains_an_unreviewed_candidate():
    b = bind(table_words(unit=False))
    assert b["cells"] and all(c["structural_status"] == "needs_review" for c in b["cells"])
    assert all(c["review_reasons"] == ["missing_or_ambiguous_unit"] for c in b["cells"])


def test_missing_shifted_duplicate_and_percentage_columns_are_not_filled_in():
    for change in ("shift", "duplicate", "percent"):
        ws = table_words()
        target = next(w for w in ws if w["text"] == "(12)")
        if change == "shift":
            target.update(x0=200, x1=220)
        elif change == "percent":
            target["text"] = "12%"
        else:
            ws.append({**target, "id": len(ws), "text": "999"})
        b = bind(ws)
        assert all(c["fields"]["label"]["text"] != "Loi nhuan" for c in b["cells"])
        assert b["skipped_rows"][0]["reason"] == "incomplete_or_duplicate_column_alignment"


def test_repeated_year_headers_and_invalid_geometry_fail_closed():
    ws = table_words()
    next(w for w in ws if w["text"] == "2023")["text"] = "2024"
    assert bind(ws)["cells"] == []
    ws[0]["x0"] = float("nan")
    with pytest.raises(ValueError, match="geometry"):
        bind(ws)


def test_separate_tables_do_not_share_years_units_or_entity_scope():
    a = table_words()
    b = table_words(unit=False)
    for w in b:
        w["x0"] += 650
        w["x1"] += 650
        w["id"] += len(a)
    result = bind_words(a + b, width=1300, height=800, content_hash="a" * 64, page_number=1)
    assert len(result["header_diagnostics"]) == 2
    right = [c for c in result["cells"] if c["header_index"] == 1]
    assert len(right) == 4 and all(c["fields"]["unit"] is None for c in right)


def synthetic_pdf(rows=1, *, unit="Trieu VND", column_units=False):
    writer = PdfWriter()
    page = writer.add_blank_page(width=600, height=800)
    font = DictionaryObject({NameObject("/Type"): NameObject("/Font"), NameObject("/Subtype"): NameObject("/Type1"),
                             NameObject("/BaseFont"): NameObject("/Helvetica")})
    page[NameObject("/Resources")] = DictionaryObject({NameObject("/Font"): DictionaryObject({NameObject("/F1"): font})})
    stream = DecodedStreamObject()
    chunks = []
    parts = [(40, 750, "Hop nhat"), (40, 690, "STT Chi tieu"),
             (278, 690, "2024"), (378, 690, "2023")]
    if unit is not None:
        parts.append((40, 720, unit))
    if column_units:
        parts.extend([(278, 674, "VND"), (378, 674, "VND")])
    for i in range(rows):
        parts.extend([(40, 650 - i * 40, f"{i + 1} Loi nhuan sau thue"),
                      (289, 650 - i * 40, "12"), (389, 650 - i * 40, "25")])
    for x, y, text in parts:
        chunks.append(f"BT /F1 10 Tf 1 0 0 1 {x} {y} Tm ({text}) Tj ET")
    stream.set_data("\n".join(chunks).encode())
    page[NameObject("/Contents")] = writer._add_object(stream)
    output = io.BytesIO()
    writer.write(output)
    return output.getvalue()


def test_pdf_replay_rejects_tampered_word_and_wrong_raw_bytes():
    raw = synthetic_pdf()
    digest = sha256(raw)
    b = extract_page(raw, digest, 1)
    assert len(b["cells"]) == 2 and replay_page(b, raw)
    forged = copy.deepcopy(b)
    forged["words"][0]["text"] = "FORGED"
    with pytest.raises(ValueError, match="differs"):
        replay_page(forged, raw)
    with pytest.raises(ValueError, match="checksum"):
        extract_page(raw + b"changed", digest, 1)
    with pytest.raises(ValueError, match="page"):
        extract_page(raw, digest, 0)


def test_cell_selector_rejects_unknown_duplicate_abstained_and_changed_model():
    context = [{"candidate_id": "a", "value": "(12)", "human_reviewed": False}]
    draft = runner.CellSelection(selected_cell_ids=["a", "a", "invented"], insufficient_evidence=False, missing_information=[])
    chosen, blocked = runner.verify_selection(draft, context, True)
    assert len(chosen) == 1 and chosen[0]["value"] == "(12)" and not chosen[0]["human_reviewed"]
    assert blocked[0]["reasons"] == ["duplicate_cell_id"] and blocked[1]["reasons"] == ["unknown_cell_id"]
    assert not runner.verify_selection(draft, context, False)[0]
    assert not runner.verify_selection(draft.model_copy(update={"insufficient_evidence": True}), context, True)[0]


def test_context_budget_and_year_filter_keep_entire_cells():
    table = bind(table_words())
    bundles = []
    for i in range(30):
        b = copy.deepcopy(table)
        for c in b["cells"]:
            c["cell_id"] = str(i) + c["cell_id"]
        bundles.append({"source": {"version_id": str(i)}, "table": b})
    profile = {"topics": {"income": {"query": ["lợi nhuận"], "anchors": ["lợi nhuận"]}}}
    context = runner.context_cells(bundles, query="lợi nhuận 2024", year="2024", retrieval_profile=profile)
    assert len(context) == 18 and all(c["year"] == "2024" and c["value"] == "(12)" for c in context)
    assert len(json.dumps(context, ensure_ascii=False)) <= 9000
    assert not runner.context_cells(bundles, query="lợi nhuận 2025", year="2025", retrieval_profile=profile)


def test_short_model_ids_keep_hash_mapping_out_of_prompt_and_reject_unknown_refs():
    context = [{"candidate_id": "a" * 64, "cell_id": "b" * 64, "label": "loi nhuan", "value": "(12)",
                "year": "2024", "unit": "Trieu VND", "observed_statement_scope": None,
                "review_reasons": ["missing_scope"], "human_reviewed": False}]
    payload = runner.short_messages("loi nhuan 2024", "FPT", context)
    assert "a" * 64 not in str(payload) and "b" * 64 not in str(payload)
    draft = runner.ShortCellSelection(selected_cell_ids=["C1", "C1", "C18"], insufficient_evidence=False, missing_information=[])
    picked, blocked = runner.verify_short_selection(draft, context, True)
    assert picked[0]["candidate_id"] == "a" * 64 and picked[0]["model_cell_id"] == "C1"
    assert not picked[0]["human_reviewed"] and picked[0]["review_reasons"] == ["missing_scope"]
    assert [b["model_cell_id"] for b in blocked] == ["C1", "C18"]


@pytest.fixture
def runtime(tmp_path, monkeypatch):
    root = Path(__file__).resolve().parents[1]
    for name in (runner.PROFILE, runner.SELECTOR, "configs/financial_sections_v0_3.json", "configs/table_evidence_v0_5.json",
                 "configs/table_evidence_v0_6.json", "configs/table_context_v0_6.json",
                 "configs/table_evidence_v0_7.json", "configs/pdf_text_v0_7.json",
                 "configs/table_evidence_v0_8.json", "configs/table_page_policy_v0_8.json",
                 "configs/table_evidence_v0_9.json", "configs/table_units_v0_9.json", "configs/pdf_ocr_v0_1.json",
                 "configs/pdf_ocr_v0_2.json", "configs/pdf_ocr_v0_3.json", "configs/ocr_cell_links_v0_1.json",
                 "configs/ocr_cell_links_v0_2.json"):
        path = tmp_path / name
        path.parent.mkdir(exist_ok=True)
        path.write_bytes((root / name).read_bytes())
    monkeypatch.setattr(runner, "capture_repository", lambda *a: {"status": "test_fixture"})
    return tmp_path


@pytest.mark.parametrize("profile_id", ["table_cells_v0.4", "table_cells_v0.5", "table_cells_v0.6", "table_cells_v0.7", "table_cells_v0.8", "table_cells_v0.9"])
def test_empty_pit_allowlist_never_reads_raw_pdf_or_calls_model(runtime, monkeypatch, profile_id):
    def denied(*args, **kwargs):
        if profile_id in {"table_cells_v0.8", "table_cells_v0.9"}:
            from pit_haf.data.hub import file_sha
            kwargs["retrieval_trace"]["annual_page_policy"] = {
                "policy_id": "annual_table_pages_v0.8",
                "policy_sha256": file_sha(runtime / "configs/table_page_policy_v0_8.json")}
        return Corpus(), [], set(), [{"status": "missing_proof"}]
    monkeypatch.setattr(runner, "retrieve", denied)
    monkeypatch.setattr(runner, "extract_page", lambda *a: pytest.fail("raw PDF touched"))
    monkeypatch.setattr(runner, "extract_page_v05", lambda *a: pytest.fail("raw PDF touched"))
    folder, result = runner.run(runtime, query="loi nhuan 2024", ticker="FPT", mode="strict_point_in_time",
                                decision_at="2024-12-31T00:00:00Z", use_model=True, adapter=object(), profile_id=profile_id)
    assert result["status"] == "abstained_no_table_context" and result["llm_calls"] == 0
    assert runner.replay(runtime, folder)["human_reviewed_facts"] == 0
    with pytest.raises(ValueError, match="annual"):
        runner.run(runtime, query="loi nhuan quy 1 2024", ticker="FPT")


@pytest.fixture
def saved_table_run(runtime, monkeypatch, request):
    grouped = getattr(request, "param", None) == "grouped_v06"
    raw = synthetic_pdf(rows=3 if grouped else 1)
    store = SnapshotStore(runtime / "data/cache/evidence")
    digest = store.put_blob(raw)
    version = EvidenceVersion(record_id="synthetic", version_id="v1", source_id="fixture", ticker="FPT",
                              source_url="https://fixture.example/pdf", document_type="annual_report", title="Fixture",
                              reporting_period="2024", content_hash=digest, retrieved_at="2026-10-24T00:00:00Z",
                              system_recorded_at="2026-10-24T00:00:00Z")
    store.register(version)
    text = "Fixture financial source"
    page = EvidencePage(record_id=version.record_id, version_id=version.version_id, content_hash=digest,
                        ticker="FPT", source_url=version.source_url, page=1, text=text, text_hash=sha256(text.encode()),
                        extractor="fixture", extraction_status="text_present", retrieved_at=version.retrieved_at,
                        data_kind="real_document")
    hit = Passage("v1", "synthetic", "FPT", 1, 0, len(text), text, page.text_hash, 1)
    monkeypatch.setattr(runner, "retrieve", lambda *a, **kw: (Corpus((version,), (page,)), [hit], None, []))
    calls = []

    def transport(url, payload, timeout):
        endpoint = url.rsplit("/", 1)[1]
        if endpoint == "chat":
            calls.append(json.loads(payload))
            context = json.loads(calls[-1]["messages"][1]["content"])["unreviewed_table_cells"]
            output = {"selected_cell_ids": [context[0]["cell_id"]], "insufficient_evidence": False, "missing_information": []}
            value = {"done": True, "message": {"content": json.dumps(output)}}
        else:
            value = {"version": "fixture", "models": [{"name": "qwen3:4b", "digest": "a" * 64}]}
        return HttpReply(200, json.dumps(value).encode(), {})

    adapter = OllamaAdapter(OllamaConfig(num_ctx=4096, num_predict=512, max_retries=0), transport=transport)
    folder, result = runner.run(runtime, query="loi nhuan 2024", ticker="FPT", use_model=True, adapter=adapter,
                                profile_id="table_cells_v0.6" if grouped else "table_cells_v0.4")
    assert result["status"] == "selected_candidates_unreviewed" and len(calls) == 1
    return runtime, folder, result


@pytest.mark.parametrize("saved_table_run", ["grouped_v06"], indirect=True)
def test_grouped_source_alternatives_and_context_audit_replay(saved_table_run):
    from pit_haf.research.table_views import detail

    root, folder, result = saved_table_run
    assert runner.replay(root, folder) == result
    view = detail(root, result["run_id"])
    assert len(view["cells"]) == 1 and len(view["cells"][0]["source_alternatives"]) == 3
    assert len({tuple(a["fields"]["value"]["bbox"]) for a in view["cells"][0]["source_alternatives"]}) == 3
    assert view["context_audit"]["grouped_duplicate_cells"] == 2
    audit = folder / "context-audit.json"
    data = json.loads(audit.read_text(encoding="utf-8"))
    data["input_year_cells"] += 1
    audit.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="checksum"):
        runner.replay(root, folder)


def test_full_raw_request_response_pdf_replay_and_manifest_tamper(saved_table_run):
    runtime, folder, result = saved_table_run
    assert runner.replay(runtime, folder) == result
    path = folder / "table-01.json"
    b = json.loads(path.read_text(encoding="utf-8"))
    b["table"]["cells"][0]["fields"]["value"]["text"] = "999"
    path.write_text(json.dumps(b), encoding="utf-8")
    with pytest.raises(ValueError, match="checksum"):
        runner.replay(runtime, folder)
    integrity = json.loads((folder / "integrity.json").read_text())
    integrity["files"][path.name] = sha256(path.read_bytes())
    (folder / "integrity.json").write_text(json.dumps(integrity))
    with pytest.raises(ValueError, match="differs"):
        runner.replay(runtime, folder)


def test_table_api_checks_saved_geometry_images_and_render_bounds(saved_table_run):
    from fastapi.testclient import TestClient

    from pit_haf.ui.api import create_app

    root, folder, result = saved_table_run
    with TestClient(create_app(root)) as client:
        history = client.get("/api/research/table-evidence").json()["runs"]
        assert history[0]["run_id"] == result["run_id"]
        endpoint = "/api/research/table-evidence/" + result["run_id"]
        view = client.get(endpoint)
        assert view.status_code == 200
        view = view.json()
        assert view["replay"] == "passed" and view["human_reviewed_facts"] == 0
        assert view["cells"][0]["fields"]["value"]["bbox"]
        assert view["cells"][0]["model_selected"] and view["cells"][0]["context_ref"] == "C1"
        assert view["sources"][0]["extracted_cells"] > 0
        assert isinstance(view["sources"][0]["stop_reasons"], list)
        image = client.get(endpoint + "/pages/1/image")
        assert image.status_code == 200 and image.content.startswith(b"\x89PNG\r\n\x1a\n")
        assert client.get(endpoint + "/pages/0/image").status_code == 404
        assert client.get(endpoint + "/pages/4/image").status_code == 404
        assert client.get("/api/research/table-evidence/bad-id").status_code == 503
        (folder / "context.json").write_text("[]")
        assert client.get(endpoint).status_code == 503


def test_table_api_defaults_to_no_model_and_v06_and_applies_origin_gate(saved_table_run, monkeypatch):
    from fastapi.testclient import TestClient

    from pit_haf.ui import api as api_module

    root, _, result = saved_table_run
    calls = []

    def stub(*args, **kwargs):
        calls.append(kwargs)
        return None, result

    monkeypatch.setattr(api_module, "run_table_evidence", stub)
    with TestClient(api_module.create_app(root)) as client:
        response = client.post("/api/research/table-evidence", json={"ticker": "FPT", "query": "loi nhuan 2024"})
        assert response.status_code == 200 and len(calls) == 1
        assert calls[0]["profile_id"] == "table_cells_v0.6" and calls[0]["use_model"] is False
        assert client.post("/api/research/table-evidence", json={"ticker": "FPT", "query": "loi nhuan 2024"},
                           headers={"Origin": "https://untrusted.example"}).status_code == 403
        assert len(calls) == 1
        assert client.post("/api/research/table-evidence", json={"ticker": "FPT", "query": "loi nhuan 2024",
                                                                 "profile_id": "made-up"}).status_code == 422
