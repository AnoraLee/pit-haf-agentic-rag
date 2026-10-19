"""Temporary synthetic review records only; never label real development cases."""

import json

import pytest
from fastapi.testclient import TestClient

from pit_haf.data.retrieval_scope import resolve_scope
from pit_haf.llm.ollama import sha256
from pit_haf.research.reports import ReportDraft, verify_claims
from pit_haf.research.reviews import (
    ReviewConflict,
    ReviewInput,
    case_detail,
    ledger,
    list_cases,
    save_review,
)
from pit_haf.ui.api import create_app


@pytest.mark.parametrize("question,period,expected,basis", [
    ("lợi nhuận năm 2024", None, "2024", "question"),
    ("kết quả quý II năm 2024", None, "2024-Q2", "question"),
    ("Q3 2024", None, "2024-Q3", "question"),
    ("so sánh năm 2023 và 2024", None, None, "ambiguous_question"),
    ("kế hoạch năm 2025", "2024", "2024", "explicit"),
    ("năm 2024", "all", None, "unrestricted"),
])
def test_period_resolution_is_explicit_and_does_not_guess_ambiguous_years(question, period, expected, basis):
    scope = resolve_scope(question, "VCB", reporting_period=period)
    assert scope.reporting_period == expected and scope.period_basis == basis


def test_observed_entity_label_guard_does_not_treat_related_company_as_issuer():
    selected = [{"evidence_id": "S1", "passage": {"text": "VCBS có lợi nhuận 100 tỷ đồng."}}]
    draft = ReportDraft(claims=[{"evidence_id": "S1", "statement": "VCBS có lợi nhuận 100 tỷ đồng.",
                                "quote": "VCBS có lợi nhuận 100 tỷ đồng.", "extracted_numbers": []}],
                        missing_information=[], insufficient_evidence=False)
    accepted, rejected = verify_claims(draft, selected, True, entity_review_labels=["VCBS"])
    assert not accepted and "named_entity_requires_review" in rejected[0]["verification"]["block_reasons"]


@pytest.fixture
def review_root(tmp_path):
    pack_id = "20261019T010203Z-abcdef12"
    case = {"case_id": "synthetic-case", "ticker": "FPT", "question": "Synthetic fixture question",
            "evidence": [{"evidence_id": "S1", "source": {"version_id": "synthetic-v1", "source_url": "https://fixture.example"},
                          "passage": {"text": "Doanh thu giả lập đạt 100 tỷ đồng.", "start": 10, "page": 1, "page_text_hash": "a" * 64}}]}
    pack = tmp_path / "outputs/development-cases" / pack_id
    pack.mkdir(parents=True)
    raw = (json.dumps(case) + "\n").encode()
    (pack / "cases.jsonl").write_bytes(raw)
    index = {"pack_id": pack_id, "cases": 1, "cases_sha256": sha256(raw)}
    (pack / "summary.json").write_text(json.dumps(index))
    public = tmp_path / "data/development/v0.2"
    public.mkdir(parents=True)
    (public / "case_index.json").write_text(json.dumps(index))
    return tmp_path, pack_id, pack


def review(pack_id, **updates):
    return ReviewInput(pack_id=pack_id, case_id="synthetic-case", **({
        "status": "answered", "reviewer": "Synthetic reviewer fixture", "declaration": True,
        "answers": [{"evidence_id": "S1", "statement": "Doanh thu giả lập đạt 100 tỷ đồng.",
                     "quote": "Doanh thu giả lập đạt 100 tỷ đồng.", "extracted_numbers": ["100 tỷ đồng"]}],
    } | updates))


def test_review_requires_declaration_and_supported_answer_then_appends_revisions(review_root):
    root, pack_id, _ = review_root
    assert list_cases(root)["declared_reviewed_cases"] == 0
    with pytest.raises(ValueError, match="explicitly declare"):
        save_review(root, review(pack_id, declaration=False))
    bad = review(pack_id).model_dump()
    bad["answers"][0]["statement"] = "Doanh thu giả lập đạt 999 tỷ đồng."
    with pytest.raises(ValueError, match="literal quote"):
        save_review(root, ReviewInput(**bad))
    first = save_review(root, review(pack_id))
    path, _ = ledger(root, pack_id)
    original = path.read_bytes()
    with pytest.raises(ReviewConflict):
        save_review(root, review(pack_id))
    second = save_review(root, review(pack_id, previous_revision=first["revision"], notes="Synthetic fixture revision"))
    assert path.read_bytes().startswith(original) and len(path.read_bytes().splitlines()) == 2
    assert second["revision"] != first["revision"] and second["previous_revision"] == first["revision"]
    assert list_cases(root)["declared_reviewed_cases"] == 1
    assert not second["independent_semantic_validation"] and not second["historical_availability_validated"]


def test_changed_source_or_corrupt_review_chain_cannot_be_silently_reused(review_root):
    root, pack_id, pack = review_root
    first = save_review(root, review(pack_id))
    save_review(root, review(pack_id, previous_revision=first["revision"], notes="Synthetic second review"))
    path, _ = ledger(root, pack_id)
    rows = path.read_bytes().splitlines(keepends=True)
    path.write_bytes(rows[1])
    with pytest.raises(ValueError, match="revision chain"):
        ledger(root, pack_id)
    (pack / "cases.jsonl").write_bytes((pack / "cases.jsonl").read_bytes() + b"changed")
    with pytest.raises(ValueError, match="source checksum"):
        case_detail(root, "synthetic-case")


def test_review_api_preserves_pending_rows_enforces_origin_and_detects_stale_save(review_root):
    root, pack_id, _ = review_root
    client = TestClient(create_app(root))
    assert client.get("/api/research/cases").json()["declared_reviewed_cases"] == 0
    assert client.get("/api/research/cases/synthetic-case").json()["review"] is None
    body = review(pack_id).model_dump()
    assert client.post("/api/research/reviews", json=body, headers={"Origin": "https://untrusted.example"}).status_code == 403
    assert client.post("/api/research/reviews", json=body).status_code == 200
    assert client.post("/api/research/reviews", json=body).status_code == 409
    exported = client.get("/api/research/reviews/export").json()
    assert exported["annotations"][0]["status"] == "answered"
    assert client.get("/api/research/cases/missing").status_code == 404


def test_old_review_cannot_attach_to_replaced_cases_even_if_pack_metadata_is_rewritten(review_root):
    root, pack_id, pack = review_root
    save_review(root, review(pack_id))
    case = json.loads((pack / "cases.jsonl").read_text())
    case["question"] = "Synthetic replacement question"
    raw = (json.dumps(case) + "\n").encode()
    (pack / "cases.jsonl").write_bytes(raw)
    for path in (pack / "summary.json", root / "data/development/v0.2/case_index.json"):
        metadata = json.loads(path.read_text())
        metadata["cases_sha256"] = sha256(raw)
        path.write_text(json.dumps(metadata))
    with pytest.raises(ValueError, match="different source snapshot"):
        list_cases(root)
