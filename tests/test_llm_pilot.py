"""Offline contract/scoring fixtures are excluded from real-document pilot metrics."""

import json

import pytest

from pit_haf.llm.ollama import OllamaConfig
from pit_haf.llm.pilot import (
    PilotCase,
    aggregate,
    build_messages,
    check_output,
    load_cases,
    number_supported,
    run_pilot,
)


def case(**changes):
    return PilotCase(**{
        "sample_id": "fixture-01", "data_kind": "smoke_fixture", "ticker": "TEST",
        "record_id": "fixture", "version_id": "fixture-v1", "content_hash": "a" * 64,
        "source_url": "https://example.invalid/fixture.pdf", "page": 1,
        "context": "Doanh thu 120 tỷ đồng. Lợi nhuận 12 tỷ đồng.",
        "expected_quote": "Lợi nhuận 12 tỷ đồng.", "expected_numbers": ["12 tỷ đồng"], **changes,
    })


def output(**changes):
    return {"quote": "Lợi nhuận 12 tỷ đồng.", "extracted_numbers": ["12 tỷ đồng"],
            "summary": "Lợi nhuận đạt 12 tỷ đồng.", "insufficient_evidence": False, **changes}


def cases_file(tmp_path, cases):
    path = tmp_path / "cases.jsonl"
    path.write_text("\n".join(item.model_dump_json() for item in cases), encoding="utf-8")
    return path


def test_real_pilot_refuses_smoke_and_mixed_input_before_network(tmp_path):
    path = cases_file(tmp_path, [case()])
    with pytest.raises(ValueError, match="real_document required"):
        load_cases(path, smoke=False)
    assert len(load_cases(path, smoke=True)) == 1
    path = cases_file(tmp_path, [case(), case(sample_id="real", data_kind="real_document")])
    with pytest.raises(ValueError, match="smoke_fixture required"):
        load_cases(path, smoke=True)


def test_duplicate_ids_and_empty_cases_are_rejected(tmp_path):
    with pytest.raises(ValueError, match="Duplicate"):
        load_cases(cases_file(tmp_path, [case(), case()]), smoke=True)
    with pytest.raises(ValueError, match="At least one"):
        load_cases(cases_file(tmp_path, []), smoke=True)


def test_gold_is_not_sent_to_model():
    messages = build_messages(case())
    request = json.dumps(messages)
    assert "expected_quote" not in request and "expected_numbers" not in request
    assert "content_hash" not in request
    assert json.loads(messages[1]["content"])["context"] == case().context


@pytest.mark.parametrize("value,text,supported", [
    ("12", "120 tỷ", False), ("12", "1.12", False),
    ("12 tỷ đồng", "Lợi nhuận 12 tỷ đồng.", True),
    ("12 tỷ đồng", "Lợi nhuận 12 tỷ đồng", True),
    ("(1.234)", "Lỗ (1.234) triệu đồng", True),
    ("1.234", "Lỗ (1.234) triệu đồng", False),
    ("1.234", "Lỗ ( 1.234 ) triệu đồng", False),
    ("1.234", "Lỗ - 1.234 triệu đồng", False),
    ("1.234", "Lỗ − 1.234 triệu đồng", False),
    ("1.234", "Lỗ -1.234 triệu đồng", False),
    ("-1.234", "Lỗ -1.234 triệu đồng", True),
    ("- 1.234", "Lỗ - 1.234 triệu đồng", True),
    ("( 1.234 )", "Lỗ ( 1.234 ) triệu đồng", True),
    ("(1.234", "Lỗ (1.234) triệu đồng", False),
    ("1.234)", "Lỗ (1.234) triệu đồng", False),
    ("tỷ đồng", "120 tỷ đồng", False), ("", "120", False),
])
def test_numeric_match_does_not_accept_partial_or_non_numeric_span(value, text, supported):
    assert number_supported(value, text) is supported


def test_exact_quote_and_numbers_are_required_but_not_semantic_summary_proof():
    checks = check_output(case(), output())
    assert checks["accepted"] and checks["gold_numeric_matches"] == 1
    assert checks["semantic_summary_support"] == "not_assessed"
    assert not check_output(case(), output(quote="Lợi nhuận 13 tỷ đồng."))["accepted"]
    assert not check_output(case(), output(extracted_numbers=["120 tỷ đồng"]))["accepted"]


def test_consistent_abstention_is_kept_separately_from_accepted_extraction():
    checks = check_output(case(), output(quote="", extracted_numbers=[], insufficient_evidence=True))
    assert checks["abstained"] and checks["abstention_consistent"]
    assert not checks["accepted"]


def test_failed_cases_remain_in_success_denominator_and_absent_tokens_are_not_zero():
    good = {"checks": check_output(case(), output()), "generation": {
        "wall_seconds": 2, "attempts": [{"status": "schema_valid", "usage": {"eval_count": 5}}],
    }}
    failed = {"checks": check_output(case(), None), "generation": {
        "wall_seconds": 3, "attempts": [{"status": "failed", "failure": "oom", "usage": None}],
    }}
    result = aggregate([good, failed])
    assert result["sample_denominator"] == 2 and result["schema_valid_rate_all_samples"] == .5
    assert result["attempt_failures"] == {"oom": 1}
    assert result["observed_output_tokens_all_attempts"] == 5
    assert result["token_counts_missing_attempts"] == 1
    assert result["numeric_gold_scored_schema_valid_samples"] == 1
    assert aggregate([failed])["observed_output_tokens_all_attempts"] is None


def test_model_digest_change_invalidates_run_without_losing_raw_results(tmp_path, monkeypatch):
    from pit_haf.llm import pilot
    monkeypatch.setattr(pilot, "capture_repository", lambda *args: {"status": "fixture"})
    class Adapter:
        inspections = 0
        def inspect(self, destination):
            self.inspections += 1
            return {"digest": ("a" if self.inspections == 1 else "b") * 64}
        def extract(self, messages, destination):
            destination.mkdir(parents=True)
            return {"output": output(), "wall_seconds": 1,
                    "attempts": [{"status": "schema_valid", "usage": None}]}
    destination = run_pilot(cases_file(tmp_path, [case()]), tmp_path / "output", OllamaConfig(),
                            smoke=True, adapter=Adapter(), repository_root=tmp_path)
    manifest = json.loads((destination / "manifest.json").read_text())
    metrics = json.loads((destination / "metrics.json").read_text())
    assert manifest["status"] == "model_changed_invalid_run"
    assert metrics["real_document_metrics"] is False and not metrics["model_identity_validated"]
    assert (destination / "results.jsonl").is_file()


def test_interruption_keeps_completed_results_and_unattempted_counts(tmp_path, monkeypatch):
    from pit_haf.llm import pilot
    monkeypatch.setattr(pilot, "capture_repository", lambda *args: {"status": "fixture"})
    class Adapter:
        def inspect(self, destination):
            return {"digest": "a" * 64}
        def extract(self, messages, destination):
            raise KeyboardInterrupt()
    with pytest.raises(KeyboardInterrupt):
        run_pilot(cases_file(tmp_path, [case()]), tmp_path / "output", OllamaConfig(),
                  smoke=True, adapter=Adapter(), repository_root=tmp_path)
    destination = next((tmp_path / "output").iterdir())
    manifest = json.loads((destination / "manifest.json").read_text())
    assert manifest["status"] == "interrupted" and manifest["unattempted_samples"] == 1
    assert (destination / "partial_metrics.json").is_file()
