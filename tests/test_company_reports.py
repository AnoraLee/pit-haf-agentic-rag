"""Synthetic fixtures verify source isolation and rejection; no research results."""

import json
from dataclasses import replace
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from pit_haf.data.evidence import EvidencePage, EvidenceVersion
from pit_haf.llm.ollama import HttpReply, OllamaAdapter, OllamaConfig, sha256
from pit_haf.research.casepack import check_reviews
from pit_haf.research.reports import (
    PROTOCOL,
    ReportDraft,
    run_report,
    saved_report,
    select_context,
    verify_claims,
)
from pit_haf.ui.api import create_app
from pit_haf.ui.workspace import Corpus, search_passages
from pit_haf.verification.arithmetic import calculate


@pytest.fixture
def report_source(tmp_path):
    config = tmp_path / PROTOCOL
    config.parent.mkdir(parents=True)
    config.write_bytes((Path(__file__).resolve().parents[1] / PROTOCOL).read_bytes())
    version = EvidenceVersion(record_id="synthetic-fpt", version_id="synthetic-v1", source_id="fixture",
                              source_url="https://fixture.example/report", ticker="FPT",
                              document_type="annual_report", title="Synthetic source; not real financial data",
                              content_hash="a" * 64, retrieved_at="2026-10-19T00:00:00Z",
                              system_recorded_at="2026-10-19T00:00:00Z")
    text = "Dữ liệu giả lập. Doanh thu năm 2024 đạt 100 tỷ đồng. Lợi nhuận là (12) tỷ đồng."
    page = EvidencePage(record_id=version.record_id, version_id=version.version_id, ticker="FPT",
                        content_hash=version.content_hash, page=1, text=text, text_hash=sha256(text.encode()),
                        source_url=version.source_url, retrieved_at=version.retrieved_at,
                        extractor="synthetic-fixture", extraction_status="text_present", data_kind="real_document")
    data = Corpus((version,), (page,))
    return tmp_path, data, search_passages(data, "doanh thu")


def claim(**updates):
    return {"evidence_id": "S1", "statement": "Doanh thu năm 2024 đạt 100 tỷ đồng.",
            "quote": "Doanh thu năm 2024 đạt 100 tỷ đồng.", "extracted_numbers": [], **updates}


class FixtureAdapter:
    def __init__(self, changed=False):
        self.calls, self.inspections, self.changed = [], 0, changed

    def inspect(self, destination):
        self.inspections += 1
        return {"digest": ("b" if self.changed and self.inspections > 1 else "a") * 64}

    def extract(self, messages, destination, *, schema):
        assert schema is ReportDraft
        self.calls.append(messages)
        return {"output": {"claims": [claim()], "missing_information": [], "insufficient_evidence": False},
                "wall_seconds": 0.01}


def test_single_agent_report_preserves_locators_and_keeps_audit_out_of_context(report_source):
    root, data, hits = report_source
    adapter = FixtureAdapter()
    result = run_report(root, data, hits, query="doanh thu", ticker="FPT", mode="exploratory_current",
                        retrieval_audit=[{"version_id": "FUTURE-EVALUATOR-ONLY", "status": "future"}], adapter=adapter)
    assert result["status"] == "completed_with_citations" and len(adapter.calls) == 1
    assert "FUTURE-EVALUATOR-ONLY" not in json.dumps(adapter.calls)
    assert result["semantic_support"] == "not_assessed" and not result["historical_availability_validated"]
    assert result["prediction"] == "ABSTAIN" and result["research_prediction_results"] is False
    cite = result["claims"][0]["citation"]
    assert data.pages[0].text[cite["start"]:cite["end"]] == claim()["quote"]
    assert json.loads((Path(result["path"]) / "report.json").read_text(encoding="utf-8")) == result
    assert (Path(result["path"]) / "report.md").is_file()


@pytest.mark.parametrize("override", [
    {"statement": "Doanh thu năm 2024 đạt 999 tỷ đồng."},
    {"statement": "Lợi nhuận là 12 tỷ đồng.", "quote": "Lợi nhuận là (12) tỷ đồng."},
    {"evidence_id": "S3"}, {"quote": "Doanh thu đạt 999 tỷ đồng."},
])
def test_report_rejects_forged_number_sign_quote_or_reference_even_if_numbers_list_empty(report_source, override):
    _, data, hits = report_source
    selected = select_context(data, hits, "FPT", mode="exploratory_current")
    draft = ReportDraft(claims=[claim(**override)], missing_information=[], insufficient_evidence=False)
    accepted, rejected = verify_claims(draft, selected, True)
    assert not accepted and rejected[0]["verification"]["block_reasons"]


def test_model_digest_change_blocks_every_claim(report_source):
    root, data, hits = report_source
    result = run_report(root, data, hits, query="doanh thu", ticker="FPT", mode="exploratory_current",
                        adapter=FixtureAdapter(changed=True))
    assert result["status"] == "abstained" and result["claims"] == []
    assert "model_digest_changed" in result["rejected_claims"][0]["verification"]["block_reasons"]


def test_strict_empty_cohort_stops_before_model_and_never_falls_back(report_source):
    root, data, _ = report_source
    adapter = FixtureAdapter()
    result = run_report(root, data, [], query="doanh thu", ticker="FPT", mode="strict_point_in_time",
                        decision_at="2025-01-01T00:00:00Z", allowed_versions=set(), adapter=adapter)
    assert result["status"] == "abstained" and result["llm_calls"] == 0
    assert adapter.inspections == 0 and not adapter.calls


def test_source_tampering_wrong_ticker_and_unproven_historical_version_are_rejected(report_source):
    _, data, hits = report_source
    for altered, ticker, kwargs in [
        ([replace(hits[0], text="tampered source")], "FPT", {}),
        ([replace(hits[0], end=len(data.pages[0].text) + 100)], "FPT", {}),
        (hits, "VCB", {}),
        (hits, "FPT", {"mode": "strict_point_in_time", "decision_at": "2025-01-01T00:00:00Z", "allowed_versions": {"synthetic-v1"}}),
    ]:
        with pytest.raises(ValueError):
            select_context(data, altered, ticker, **({"mode": "exploratory_current"} | kwargs))


def test_report_schema_is_enforced_by_the_audited_adapter(tmp_path):
    output = {"claims": [claim()], "missing_information": [], "insufficient_evidence": False}
    def transport(url, payload, timeout):
        request = json.loads(payload)
        assert request["format"] == ReportDraft.model_json_schema()
        return HttpReply(200, json.dumps({"done": True, "message": {"content": json.dumps(output)}}).encode(), {})
    result = OllamaAdapter(OllamaConfig(), transport).extract([], tmp_path / "report", schema=ReportDraft)
    assert result["output"] == output


def test_changed_protocol_budget_is_rejected_before_inference(report_source):
    root, data, hits = report_source
    path = root / PROTOCOL
    config = json.loads(path.read_text(encoding="utf-8"))
    config["report_budget"]["max_llm_calls"] = 99
    path.write_text(json.dumps(config), encoding="utf-8")
    with pytest.raises(ValueError, match="tested development budget"):
        run_report(root, data, hits, query="doanh thu", ticker="FPT", mode="exploratory_current")


def test_persisted_report_replays_without_inference_and_refuses_tampering(report_source):
    root, data, hits = report_source
    result = run_report(root, data, hits, query="doanh thu", ticker="FPT", mode="exploratory_current",
                        adapter=FixtureAdapter())
    assert saved_report(root, result["run_id"]) == result
    client = TestClient(create_app(root))
    assert client.get("/api/research/reports").json()["reports"][0]["claims"] == 1
    assert client.get("/api/research/reports/" + result["run_id"]).json() == result
    path = Path(result["path"]) / "report.json"
    path.write_bytes(path.read_bytes() + b"changed")
    with pytest.raises(ValueError, match="checksum"):
        saved_report(root, result["run_id"])
    assert client.get("/api/research/reports/" + result["run_id"]).status_code == 503
    with pytest.raises(ValueError, match="Invalid report ID"):
        saved_report(root, "../../outside")


def test_context_budget_is_bounded_before_any_generation(report_source):
    _, data, _ = report_source
    original = data.pages[0]
    text = (original.text + " ") * 100
    page = original.model_copy(update={"text": text, "text_hash": sha256(text.encode())})
    corpus = Corpus(data.versions, (page,))
    hits = search_passages(corpus, "doanh thu")
    selected = select_context(corpus, hits, "FPT", mode="exploratory_current")
    assert len(selected) <= 3
    assert sum(len(s["passage"]["text"]) for s in selected) <= 2100


def test_report_api_uses_same_gateway_and_rejects_cross_origin(report_source, monkeypatch):
    root, data, hits = report_source
    monkeypatch.setattr("pit_haf.ui.api.load_corpus", lambda *a: data)
    monkeypatch.setattr("pit_haf.ui.api.workspace_fingerprint", lambda *a: ())
    observed = {}
    def runner(root, data, hits, **kwargs):
        observed.update(kwargs)
        observed["hits"] = hits
        return {"status": "synthetic-fixture-only"}
    monkeypatch.setattr("pit_haf.ui.api.run_report", runner)
    client = TestClient(create_app(root))
    body = {"query": "doanh thu", "ticker": "FPT", "mode": "exploratory_current"}
    assert client.post("/api/research/report", json=body).status_code == 200
    assert observed["hits"] == hits
    assert client.post("/api/research/report", json={**body, "ticker": None}).status_code == 422
    assert client.post("/api/research/report", json=body, headers={"Origin": "https://untrusted.example"}).status_code == 403
    assert client.get("/api/research/development").json()["protocol"]["approved_for_final_experiments"] is False


def test_annotation_templates_are_pending_and_forged_review_answers_fail(report_source):
    root, data, hits = report_source
    pack = root / "casepack"
    pack.mkdir()
    selected = select_context(data, hits, "FPT", mode="exploratory_current")
    raw = json.dumps({"case_id": "fixture", "evidence": selected}) + "\n"
    (pack / "cases.jsonl").write_bytes(raw.encode())
    (pack / "summary.json").write_text(json.dumps({"cases_sha256": sha256(raw.encode())}))
    path = pack / "reviews.jsonl"
    path.write_text(json.dumps({"case_id": "fixture", "status": "pending"}))
    assert check_reviews(pack, path)["ready_for_reviewed_development_scoring"] is False
    forged = {"case_id": "fixture", "status": "answered", "reviewer": "Synthetic reviewer fixture",
              "reviewed_at": "2026-10-19T01:00:00Z", "answers": [claim(statement="Doanh thu đạt 999 tỷ đồng.")]}
    path.write_text(json.dumps(forged))
    with pytest.raises(ValueError, match="invalid literal"):
        check_reviews(pack, path)
    (pack / "cases.jsonl").write_text(raw + " ")
    with pytest.raises(ValueError, match="checksum"):
        check_reviews(pack, path)


def fact(value, metric="revenue", period="2024", **overrides):
    return {"value": value, "metric": metric, "period": period, "unit": "billion", "currency": "VND",
            "scope": "consolidated", "review_status": "human_reviewed", "evidence_id": "synthetic-S1", **overrides}


def test_decimal_calculations_preserve_loss_sign_and_reference_inputs():
    growth = calculate("growth_percent", fact("110"), fact("100", period="2023"))
    assert growth["value"] == "10.0" and growth["inputs"][1]["period"] == "2023"
    assert calculate("margin_percent", fact("-12", metric="net_profit"), fact("100"))["value"] == "-12.00"


@pytest.mark.parametrize("right", [fact("0", period="2023"), fact("100", period="2023", unit="million"),
                                  fact("100", period="2023", review_status="model_extracted"),
                                  fact("NaN", period="2023"), fact("100")])
def test_arithmetic_rejects_zero_incompatible_units_unreviewed_or_invalid_facts(right):
    with pytest.raises(ValueError):
        calculate("growth_percent", fact("110"), right)
