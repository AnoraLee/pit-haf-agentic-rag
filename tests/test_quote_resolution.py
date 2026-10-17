import hashlib
import json

import pytest

from pit_haf.research.quote_replay import audit_run
from pit_haf.verification.quotes import normalized_space, resolve_quote


def test_pdf_line_wrapping_resolves_to_exact_original_source_offsets():
    context = "Mở đầu. Doanh thu đạt 100 tỷ\n  đồng trong năm. Kết thúc."
    result = resolve_quote(context, "Doanh thu đạt 100 tỷ đồng trong năm.")
    assert result.mode == "whitespace_mapped"
    assert context[result.start:result.end] == result.source_quote
    assert result.source_quote == "Doanh thu đạt 100 tỷ\n  đồng trong năm."
    assert normalized_space(result.source_quote) == "Doanh thu đạt 100 tỷ đồng trong năm."


@pytest.mark.parametrize("quote", [
    "Lợi nhuận là 125 tỷ đồng.", "Lợi nhuận là (126) tỷ đồng.",
    "Lợi nhuận là (125) triệu đồng.", "Lợi nhuận là (125) tỷ đồng...",
    "Lợi nhuận là 1.25 tỷ đồng.",
])
def test_financial_sign_number_unit_and_omission_changes_cannot_be_repaired(quote):
    assert resolve_quote("Lợi nhuận là (125) tỷ đồng.", quote).mode == "not_found"


def test_repeated_literal_quote_is_ambiguous_instead_of_inventing_a_locator():
    assert resolve_quote("Doanh thu 100. Doanh thu 100.", "Doanh thu 100.").mode == "ambiguous"
    assert resolve_quote("a b. a\nb.", "a  b.").mode == "ambiguous"


def test_unicode_whitespace_can_map_but_typographic_minus_cannot_change():
    assert resolve_quote("Doanh thu\u00a0100 tỷ.", "Doanh thu 100 tỷ.").mode == "whitespace_mapped"
    assert resolve_quote("Lỗ −100 tỷ.", "Lỗ -100 tỷ.").mode == "not_found"
    assert resolve_quote("Nguồn hợp lệ", " \n\t").mode == "empty"


def preserved_fixture(tmp_path):
    source = tmp_path / "source"
    attempt = source / "samples/0001/attempt-01"
    attempt.mkdir(parents=True)
    context = "Doanh thu 100 tỷ\nđồng."
    case = dict(sample_id="smoke", data_kind="smoke_fixture", ticker="DEMO",
                record_id="smoke-record", version_id="v1", content_hash="a" * 64,
                source_url="https://example.invalid/fixture", page=1, context=context,
                expected_quote=context, expected_numbers=None)
    cases = (json.dumps(case) + "\n").encode()
    (source / "cases.jsonl").write_bytes(cases)
    output = dict(quote="Doanh thu 100 tỷ đồng.", extracted_numbers=["100 tỷ đồng"],
                  summary="Fixture summary", insufficient_evidence=False)
    raw = json.dumps({"message": {"content": json.dumps(output)}}).encode()
    request = json.dumps({"messages": [{"role": "system", "content": "Fixture"},
                                         {"role": "user", "content": json.dumps({
                                             "context": context, "record_id": "smoke-record"})}]}).encode()
    (attempt / "response.raw").write_bytes(raw)
    (attempt / "request.json").write_bytes(request)
    row = {"sample_id": "smoke", "generation": {"output": output, "attempts": [{
        "status": "schema_valid", "response_sha256": hashlib.sha256(raw).hexdigest(),
        "request_sha256": hashlib.sha256(request).hexdigest(),
    }]}}
    (source / "results.jsonl").write_text(json.dumps(row) + "\n", encoding="utf-8")
    (source / "manifest.json").write_text(json.dumps({
        "status": "completed", "model_digest_stable": True, "run_kind": "smoke_fixture",
        "input_cases_sha256": hashlib.sha256(cases).hexdigest(),
    }), encoding="utf-8")
    return source, attempt


def test_offline_replay_preserves_raw_and_reports_separate_verifier_policy(tmp_path):
    source, attempt = preserved_fixture(tmp_path)
    before = (attempt / "response.raw").read_bytes()
    destination = audit_run(source, tmp_path / "audits")
    summary = json.loads((destination / "summary.json").read_text())
    assert summary["new_inference_calls"] == 0
    assert summary["source_run_kind"] == "smoke_fixture"
    assert summary["strict_accepted"] == 0 and summary["mapped_accepted"] == 1
    assert (attempt / "response.raw").read_bytes() == before


@pytest.mark.parametrize("target", ["response.raw", "request.json", "cases.jsonl", "output"])
def test_replay_rejects_modified_inputs_and_outputs_before_scoring(tmp_path, target):
    source, attempt = preserved_fixture(tmp_path)
    if target == "output":
        path = source / "results.jsonl"
        row = json.loads(path.read_text())
        row["generation"]["output"]["summary"] = "Modified output"
        path.write_text(json.dumps(row), encoding="utf-8")
    else:
        path = (source if target == "cases.jsonl" else attempt) / target
        path.write_bytes(path.read_bytes() + b" ")
    with pytest.raises(ValueError, match="checksum|preserved raw"):
        audit_run(source, tmp_path / "audits")
