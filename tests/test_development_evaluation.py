"""Synthetic batches/annotations in temporary folders; no real cases are labelled."""

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from pit_haf.data.evidence import EvidencePage, EvidenceVersion
from pit_haf.llm.ollama import HttpReply, OllamaAdapter, OllamaConfig, sha256, write_json
from pit_haf.research.evaluation import (
    evaluate_batch,
    folder_for,
    load_batch,
    pinned_context,
    run_batch,
    span_match,
)
from pit_haf.research.reports import PROTOCOL, RETRIEVAL_POLICY, select_context
from pit_haf.research.reviews import ReviewInput, save_review
from pit_haf.ui.api import create_app
from pit_haf.ui.workspace import Corpus, search_passages

QUOTE = "Doanh thu giả lập năm 2024 đạt 100 tỷ đồng."
ANSWER = {"evidence_id": "S1", "statement": QUOTE, "quote": QUOTE, "extracted_numbers": ["100 tỷ đồng"]}


@pytest.fixture
def batch_root(tmp_path, monkeypatch):
    root = tmp_path
    for name in (PROTOCOL, RETRIEVAL_POLICY):
        target = root / name
        target.parent.mkdir(exist_ok=True)
        target.write_bytes((Path(__file__).resolve().parents[1] / name).read_bytes())
    version = EvidenceVersion(record_id="synthetic-only", version_id="fixture-v1", source_id="fixture",
                              source_url="https://fixture.example/report", ticker="FPT", document_type="annual_report",
                              title="Synthetic fixture", content_hash="a" * 64, reporting_period="2024",
                              retrieved_at="2026-10-22T00:00:00Z", system_recorded_at="2026-10-22T00:00:00Z")
    page = EvidencePage(record_id=version.record_id, version_id=version.version_id, ticker="FPT", page=1,
                        content_hash=version.content_hash, text=QUOTE, text_hash=sha256(QUOTE.encode()),
                        source_url=version.source_url, retrieved_at=version.retrieved_at,
                        extractor="synthetic-fixture", extraction_status="text_present", data_kind="real_document")
    snapshot = str(Path("outputs/milestone-1/data-pilot/fixture/summary.json"))
    data = Corpus((version,), (page,), snapshot=snapshot)
    evidence = select_context(data, search_passages(data, "doanh thu"), "FPT", mode="exploratory_current")
    cases = [{"case_id": f"fixture-{i}", "ticker": "FPT", "question": f"Câu hỏi giả lập {i}",
              "query": "doanh thu", "evidence": evidence, "retrieval_scope": {
                  "ticker": "FPT", "reporting_period": "2024", "period_basis": "explicit",
                  "source_policy": "issuer_reports", "statement_scope": "all"}} for i in range(2)]
    pack_id = "20261022T010203Z-abcdef12"
    pack = root / "outputs/development-cases" / pack_id
    pack.mkdir(parents=True)
    raw = "".join(json.dumps(c, ensure_ascii=False) + "\n" for c in cases).encode()
    (pack / "cases.jsonl").write_bytes(raw)
    summary = {"pack_id": pack_id, "cases": 2, "cases_sha256": sha256(raw), "snapshot": snapshot,
               "summary_sha256": "b" * 64, "catalog_sha256": "c" * 64,
               "protocol_sha256": sha256((root / PROTOCOL).read_bytes()),
               "retrieval_policy_sha256": sha256((root / RETRIEVAL_POLICY).read_bytes())}
    write_json(pack / "summary.json", summary)
    public = root / "data/development/v0.2"
    public.mkdir(parents=True)
    write_json(public / "case_index.json", summary)
    class FixtureCatalog:
        def __init__(self, *args):
            self.pointer = summary
        def subset(self, identities):
            assert set(identities) == {("fixture-v1", 1)}
            return data
    monkeypatch.setattr("pit_haf.research.evaluation.Catalog", FixtureCatalog)
    return root, pack_id, cases, summary, FixtureCatalog()


def adapter(outputs=None, failure=None):
    responses = iter(outputs or [{"claims": [ANSWER], "missing_information": [], "insufficient_evidence": False}] * 2)
    def transport(url, payload, timeout):
        endpoint = url.rsplit("/", 1)[-1]
        if endpoint == "chat":
            if failure:
                raise failure
            output = next(responses)
            response = {"done": True, "message": {"content": json.dumps(output)}}
        else:
            response = {"version": {"version": "fixture-only"}, "tags": {"models": [
                {"name": "qwen3:4b", "digest": "a" * 64}]}, "ps": {}, "show": {}}[endpoint]
        return HttpReply(200, json.dumps(response).encode(), {})
    return OllamaAdapter(OllamaConfig(num_ctx=4096, num_predict=1024, max_retries=0), transport)


def annotate(root, pack_id, case_id="fixture-0", **updates):
    return save_review(root, ReviewInput(**({"pack_id": pack_id, "case_id": case_id, "status": "answered",
                                           "reviewer": "Synthetic reviewer only", "declaration": True,
                                           "answers": [ANSWER]} | updates)))


def test_batch_keeps_all_rows_and_null_metrics_without_annotations(batch_root):
    root, _, _, _, _ = batch_root
    assert evaluate_batch(root)["batch"] is None
    batch = run_batch(root, limit=1, adapter=adapter())
    result = evaluate_batch(root, batch["batch_id"])
    assert result["total_cases"] == 2 and result["diagnostics"]["verified_runs"] == 1
    assert result["diagnostics"]["not_run"] == 1 and result["diagnostics"]["accepted_claims"] == 1
    assert result["semantic_accuracy"] is None
    assert result["annotation_comparison"]["reference_span_hit_rate"] is None
    assert result["declared_reviewed_cases"] == 0 and len(result["rows"]) == 2


def test_comparison_recomputes_latest_review_and_binds_revision_snapshot(batch_root):
    root, pack_id, _, _, _ = batch_root
    batch = run_batch(root, adapter=adapter())
    first = annotate(root, pack_id)
    result = evaluate_batch(root)
    assert result["annotation_comparison"]["reference_spans_hit"] == 1
    assert result["annotation_comparison"]["reference_span_hit_rate"] == 1
    assert result["annotation_comparison"]["reference_numeric_quote_hit_rate"] == 1
    assert result["independently_verified_gold_cases"] == 0
    annotate(root, pack_id, status="pending", answers=[], declaration=False, previous_revision=first["revision"])
    revised = evaluate_batch(root, batch["batch_id"])
    assert revised["review_snapshot_sha256"] != result["review_snapshot_sha256"]
    assert revised["annotation_comparison"]["reference_span_hit_rate"] is None


@pytest.mark.parametrize("artifact", ["report.json", "generation/attempt-01/request.json", "generation/attempt-01/response.raw"])
def test_corrupt_run_is_retained_as_invalid_and_excluded_from_scores(batch_root, artifact):
    root, pack_id, _, _, _ = batch_root
    batch = run_batch(root, limit=1, adapter=adapter())
    annotate(root, pack_id)
    path = root / "outputs/company-reports" / batch["cases"][0]["run_id"] / artifact
    path.write_bytes(path.read_bytes() + b"corruption")
    result = evaluate_batch(root)
    assert result["diagnostics"]["invalid_runs"] == 1
    assert result["rows"][0]["status"] == "integrity_failed" and len(result["rows"]) == 2
    assert result["annotation_comparison"]["reference_span_hit_rate"] is None


def test_technical_generation_failure_is_not_successful_nonanswer(batch_root):
    root, pack_id, _, _, _ = batch_root
    annotate(root, pack_id, status="unanswerable", answers=[], notes="Synthetic insufficient source")
    batch = run_batch(root, adapter=adapter(outputs=[{}, {}]))
    result = evaluate_batch(root, batch["batch_id"])
    assert result["diagnostics"]["generation_failed"] == 2
    assert result["annotation_comparison"].get("nonanswer_cases_compared", 0) == 0


def test_timeout_stops_batch_with_unattempted_rows_and_no_retry(batch_root):
    root, _, _, _, _ = batch_root
    batch = run_batch(root, adapter=adapter(failure=TimeoutError("Synthetic timeout")))
    assert batch["status"] == "stopped" and batch["cases"][1]["status"] == "not_run"
    result = evaluate_batch(root)
    assert result["diagnostics"]["llm_calls"] == 1
    assert result["diagnostics"]["generation_failed"] == 1
    assert not (root / "outputs/development-batches/run.lock").exists()


def test_overlap_alone_does_not_count_as_preserving_reference_numbers(batch_root):
    root, pack_id, _, _, _ = batch_root
    partial = {**ANSWER, "statement": "Doanh thu giả lập năm 2024", "quote": "Doanh thu giả lập năm 2024",
               "extracted_numbers": ["2024"]}
    output = {"claims": [partial], "missing_information": [], "insufficient_evidence": False}
    run_batch(root, limit=1, adapter=adapter(outputs=[output]))
    annotate(root, pack_id)
    comparison = evaluate_batch(root)["annotation_comparison"]
    assert comparison["reference_span_hit_rate"] == 1
    assert comparison["reference_numeric_quote_hit_rate"] == 0


def test_valid_nonanswer_is_compared_but_ocr_remains_separate(batch_root):
    root, pack_id, _, _, _ = batch_root
    output = {"claims": [], "missing_information": ["Synthetic source insufficient"], "insufficient_evidence": True}
    run_batch(root, adapter=adapter(outputs=[output, output]))
    annotate(root, pack_id, status="unanswerable", answers=[], notes="Synthetic insufficient source")
    annotate(root, pack_id, case_id="fixture-1", status="needs_ocr", answers=[], notes="Synthetic OCR case")
    comparison = evaluate_batch(root)["annotation_comparison"]
    assert comparison["nonanswer_cases_compared"] == 1
    assert comparison["nonanswer_cases_without_accepted_claims"] == 1


def test_cross_case_digest_change_stops_before_second_inference(batch_root):
    root, _, _, _, _ = batch_root
    client = adapter()
    original = client.transport
    calls = {"tags": 0, "chat": 0}
    def transport(url, payload, timeout):
        if url.endswith("/tags"):
            calls["tags"] += 1
            if calls["tags"] > 2:
                return HttpReply(200, json.dumps({"models": [{"name": "qwen3:4b", "digest": "b" * 64}]}).encode(), {})
        if url.endswith("/chat"):
            calls["chat"] += 1
        return original(url, payload, timeout)
    client.transport = transport
    batch = run_batch(root, adapter=client)
    assert calls["chat"] == 1 and batch["status"] == "stopped"
    assert batch["cases"][1]["status"] == "failed"


def test_existing_batch_lock_is_not_removed_or_reused(batch_root):
    root, _, _, _, _ = batch_root
    lock = root / "outputs/development-batches/run.lock"
    lock.parent.mkdir(parents=True)
    lock.write_text("Synthetic existing process")
    with pytest.raises(FileExistsError):
        run_batch(root, adapter=adapter())
    assert lock.read_text() == "Synthetic existing process"


def test_source_failure_remains_in_coverage_while_other_cases_run(batch_root, monkeypatch):
    root, _, _, _, _ = batch_root
    from pit_haf.research import evaluation
    original = evaluation.pinned_context
    def read(summary, case, catalog):
        if case["case_id"] == "fixture-0":
            raise ValueError("Synthetic source corruption")
        return original(summary, case, catalog)
    monkeypatch.setattr(evaluation, "pinned_context", read)
    run_batch(root, adapter=adapter())
    result = evaluate_batch(root)
    assert result["diagnostics"]["source_or_runner_failed"] == 1
    assert result["diagnostics"]["verified_runs"] == 1
    assert result["rows"][0]["error"] == "Synthetic source corruption"


def test_pinned_context_refuses_changed_text_before_model_call(batch_root):
    _, _, cases, summary, catalog = batch_root
    case = {**cases[0], "evidence": json.loads(json.dumps(cases[0]["evidence"]))}
    case["evidence"][0]["passage"]["text"] = "Synthetic tampered source"
    with pytest.raises(ValueError, match="mismatch"):
        pinned_context(summary, case, catalog)


def test_span_overlap_checks_source_page_hash_and_actual_intersection():
    cite = {"version_id": "fixture", "page": 1, "page_text_hash": "a" * 64, "start": 10, "end": 20}
    assert span_match({"citation": cite}, {"citation": {**cite, "start": 15}})
    for changes in ({"start": 20, "end": 30}, {"page": 2}, {"page_text_hash": "b" * 64}, {"version_id": "other"}):
        assert not span_match({"citation": cite}, {"citation": {**cite, **changes}})


def test_batch_seal_coverage_and_cross_pack_are_checked(batch_root):
    root, _, _, _, _ = batch_root
    batch = run_batch(root, limit=1, adapter=adapter())
    folder = folder_for(root, batch["batch_id"])
    manifest = folder / "manifest.json"
    manifest.write_bytes(manifest.read_bytes() + b" ")
    with pytest.raises(ValueError, match="checksum"):
        load_batch(root, batch["batch_id"])
    batch["cases"] = batch["cases"][:1]
    write_json(manifest, batch)
    write_json(folder / "integrity.json", {"manifest_sha256": sha256(manifest.read_bytes())})
    with pytest.raises(ValueError, match="every case"):
        evaluate_batch(root)
    batch["cases_sha256"] = "e" * 64
    write_json(manifest, batch)
    write_json(folder / "integrity.json", {"manifest_sha256": sha256(manifest.read_bytes())})
    with pytest.raises(ValueError, match="different source pack"):
        evaluate_batch(root)
    with pytest.raises(ValueError, match="Invalid batch ID"):
        folder_for(root, "../../other")


def test_evaluation_api_does_not_infer_and_reports_integrity_errors(batch_root):
    root, _, _, _, _ = batch_root
    client = TestClient(create_app(root))
    ready = client.get("/api/research/evaluation").json()
    assert ready["batch"] is None
    assert [row["question"] for row in ready["rows"]] == [c["question"] for c in batch_root[2]]
    assert all(row["status"] == "not_run" for row in ready["rows"])
    batch = run_batch(root, adapter=adapter())
    response = client.get("/api/research/evaluation").json()
    assert response["diagnostics"]["verified_runs"] == 2
    assert [row["question"] for row in response["rows"]] == [c["question"] for c in batch_root[2]]
    assert client.get("/api/research/evaluation?batch_id=invalid").status_code == 422
    manifest = folder_for(root, batch["batch_id"]) / "manifest.json"
    manifest.write_bytes(b"invalid")
    assert client.get("/api/research/evaluation").status_code == 503


@pytest.fixture
def assistant_audit_root(batch_root, monkeypatch):
    from pit_haf.research import source_audit
    root, _, cases, summary, catalog = batch_root
    data = catalog.subset({("fixture-v1", 1)})
    state = {"page": data.pages[0]}
    class AuditCatalog:
        def __init__(self, *args):
            self.pointer = summary
        def page(self, version_id, number):
            assert (version_id, number) == ("fixture-v1", 1)
            return data.versions[0], state["page"], {}
    monkeypatch.setattr(source_audit, "Catalog", AuditCatalog)
    batch = run_batch(root, adapter=adapter())
    spec = {"provenance": "assistant_source_audit", "independent_human_gold": False,
            "batch_id": batch["batch_id"], "method": "Synthetic audit fixture only",
            "rows": [{"case_id": c["case_id"], "answer": "Synthetic assistant answer",
                      "context_status": "sufficient", "context_note": "Synthetic context note",
                      "verdict": "useful_claims", "model_note": "Synthetic judgement",
                      "references": [{"page": 1, "terms": [QUOTE]}]} for c in cases]}
    folder = root / source_audit.LOCATION
    folder.mkdir(parents=True)
    write_json(folder / "answers.json", spec)
    return root, spec, state, batch


def test_assistant_audit_is_bound_read_only_and_does_not_promote_human_reviews(assistant_audit_root):
    from pit_haf.research.source_audit import REPORT, load_source_audit, publish
    root, _, _, batch = assistant_audit_root
    run_files = {p: p.read_bytes() for p in (root / "outputs/company-reports").rglob("*") if p.is_file()}
    result = publish(root)
    assert load_source_audit(root) == result
    assert result["summary"]["answered_cases"] == 2
    assert result["semantic_accuracy"] is None and not result["independent_human_gold"]
    span = result["rows"][0]["citations"][0]["spans"][0]
    assert span["quote"] == QUOTE[span["start"]:span["end"]]
    assert "trợ lý soạn" in (root / REPORT).read_text(encoding="utf-8")
    assert all(p.read_bytes() == content for p, content in run_files.items())
    assert not (root / "outputs/development-reviews").exists()
    evaluation = evaluate_batch(root, batch["batch_id"])
    assert evaluation["declared_reviewed_cases"] == 0
    assert evaluation["independently_verified_gold_cases"] == 0
    assert evaluation["annotation_comparison"]["reference_span_hit_rate"] is None


@pytest.mark.parametrize("change", ["missing_case", "duplicate_case", "foreign_case", "bad_anchor", "human_provenance"])
def test_assistant_audit_refuses_invalid_coverage_anchors_or_provenance(assistant_audit_root, change):
    from pit_haf.research.source_audit import LOCATION, publish
    root, spec, _, _ = assistant_audit_root
    if change == "missing_case":
        spec["rows"].pop()
    elif change == "duplicate_case":
        spec["rows"][1] = spec["rows"][0]
    elif change == "foreign_case":
        spec["rows"][0]["case_id"] = "unrelated-case"
    elif change == "bad_anchor":
        spec["rows"][0]["references"][0]["terms"] = ["Invented fixture quote"]
    else:
        spec["independent_human_gold"] = True
    write_json(root / LOCATION / "answers.json", spec)
    with pytest.raises(ValueError):
        publish(root)


@pytest.mark.parametrize("artifact", ["audit.json", "answers.json", "report", "model_response", "source_page"])
def test_assistant_audit_detects_drift_in_every_dependency(assistant_audit_root, artifact):
    from pit_haf.research.source_audit import LOCATION, REPORT, load_source_audit, publish
    root, _, state, batch = assistant_audit_root
    publish(root)
    if artifact == "source_page":
        text = state["page"].text + " Synthetic changed extraction"
        state["page"] = state["page"].model_copy(update={"text": text, "text_hash": sha256(text.encode())})
    else:
        if artifact == "report":
            path = root / REPORT
        elif artifact == "model_response":
            path = root / "outputs/company-reports" / batch["cases"][0]["run_id"] / "generation/attempt-01/response.raw"
        else:
            path = root / LOCATION / artifact
        path.write_bytes(path.read_bytes() + b" ")
    with pytest.raises(ValueError):
        load_source_audit(root)


def test_assistant_audit_api_is_optional_and_fails_closed(assistant_audit_root):
    from pit_haf.research.source_audit import LOCATION, publish
    root, _, _, _ = assistant_audit_root
    empty = TestClient(create_app(root / "empty-workspace"))
    assert empty.get("/api/research/source-audit").json() == {"audit": None}
    publish(root)
    client = TestClient(create_app(root))
    response = client.get("/api/research/source-audit")
    assert response.status_code == 200
    assert response.json()["audit"]["provenance"] == "assistant_source_audit"
    assert client.post("/api/research/source-audit", json={}).status_code == 405
    (root / LOCATION / "audit.json").write_bytes(b"corrupt")
    assert client.get("/api/research/source-audit").status_code == 503
