"""Synthetic year/header tests; no issuer/page/answer mapping or real manual labels."""

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from test_pdf_text import pdf_catalog  # noqa: F401
from test_table_evidence import runtime  # noqa: F401

from pit_haf.data.hub import file_sha
from pit_haf.data.pdf_text import search_annual_pdf_text
from pit_haf.data.retrieval_scope import resolve_scope
from pit_haf.data.table_page_policy import (
    POLICY,
    inspect_headers,
    load_policy,
    page_check,
    verify_selected,
)
from pit_haf.llm.ollama import write_json
from pit_haf.research import table_evidence as runner


@pytest.fixture
def policy():
    return load_policy(Path(__file__).resolve().parents[1])


@pytest.mark.parametrize("text,expected", [
    ("31/12/2023 31/12/2023 Chênh lệch\nTriệu VND Triệu VND Triệu VND\n", ["2023"]),
    ("Năm 2024 Năm 2023\nTriệu VND\n", ["2023", "2024"]),
    ("STT Chỉ tiêu Thuyết minh 2024\nTriệu VND\n2023\nTriệu VND", ["2023", "2024"]),
    ("31/12/2024\nĐơn vị: Triệu VND", ["2024"]),
    ("2024 2023 Chênh lệch\nTriệu VND", ["2023", "2024"]),
    ("Ngày 15 tháng 1 năm 2025, quyết định cho năm 2024\nTriệu VND", []),
    ("Ngày 31/12/2024, đơn vị ghi nhận 100 triệu VND", []),
    ("BÁO CÁO THƯỜNG NIÊN 2024\nTriệu VND", []),
    ("Năm 2024 so với năm 2023 tăng 10 triệu VND", []),
    ("Lợi nhuận năm 2024 đạt 100 triệu VND", []),
    ("2024 2023\nKhông có đơn vị tiền tệ", []),
    ("31/12/2023 31/12/2023 Chênh lệch\nTriệu VND\n"
     "Sự kiện sau ngày 31/12/2024\nBÁO CÁO THƯỜNG NIÊN 2024", ["2023"]),
])
def test_column_headers_exclude_body_footer_and_approval_years(policy, text, expected):
    assert inspect_headers(text, policy)["years"] == expected


def test_numeric_pages_require_requested_header_and_preserve_source_text(policy):
    page = SimpleNamespace(text="31/12/2023 31/12/2023 Chênh lệch\nTriệu VND\nLợi nhuận 2024 (narrative)")
    before = page.text
    assert page_check(page, "2024", "income", policy)["reason"] == "header_period_mismatch"
    assert page_check(SimpleNamespace(text="Lợi nhuận 2024 đạt 100 triệu VND"), "2024", "income", policy)["reason"] == "missing_year_header"
    assert page_check(page, "2023", "income", policy)["eligible"]
    assert page_check(page, "2024", "risk", policy)["eligible"]
    assert page.text == before


def test_gate_is_applied_after_scope_and_allowlist_and_empty_gate_skips_reads(pdf_catalog, monkeypatch):  # noqa: F811
    root = pdf_catalog.root
    scope = resolve_scope("lợi nhuận 2024", "AAA")
    data, hits, trace = search_annual_pdf_text(pdf_catalog, "lợi nhuận 2024", scope=scope, allowed_versions={"current"})
    assert hits and {p.version_id for p in data.pages} == {"current"}
    assert trace["annual_page_policy"]["policy_sha256"] == file_sha(root / POLICY)
    assert trace["page_year_checks"][0]["eligible"]
    monkeypatch.setattr(pdf_catalog, "connect", lambda: pytest.fail("Empty allowlist read pages"))
    assert not search_annual_pdf_text(pdf_catalog, "lợi nhuận 2024", scope=scope, allowed_versions=set())[1]


@pytest.mark.parametrize("profile", ["table_cells_v0.8", "table_cells_v0.9"])
def test_v08_run_replays_and_changed_policy_cannot_be_silently_reused(pdf_catalog, profile):  # noqa: F811
    root = pdf_catalog.root
    folder, result = runner.run(root, query="lợi nhuận 2024", ticker="AAA", profile_id=profile)
    assert result["status"] == "extracted_unreviewed" and result["llm_calls"] == 0
    assert runner.replay(root, folder) == result
    from pit_haf.research.table_views import detail
    check = detail(root, result["run_id"])["page_selection"]
    assert check["pages_checked"] == 1 and check["wrong_period_pages"] == check["missing_header_pages"] == 0
    p = json.loads((root / POLICY).read_text(encoding="utf-8"))
    p["unit_phrases"].append("other")
    write_json(root / POLICY, p)
    with pytest.raises(ValueError, match="policy checksum"):
        runner.replay(root, folder)


def test_v09_run_pins_unit_policy_and_changed_rules_are_rejected(pdf_catalog):  # noqa: F811
    root = pdf_catalog.root
    folder, result = runner.run(root, query="lợi nhuận 2024", ticker="AAA", profile_id="table_cells_v0.9")
    from pit_haf.data.pdf_tables_v09 import POLICY
    assert result["unit_policy_sha256"] == file_sha(root / POLICY)
    assert result["context_cells"] > 0 and runner.replay(root, folder) == result
    rules = json.loads((root / POLICY).read_text(encoding="utf-8"))
    rules["allow_numeric_rescaling"] = True
    write_json(root / POLICY, rules)
    with pytest.raises(ValueError, match="currency unit policy"):
        runner.replay(root, folder)


def test_replay_gate_rejects_wrong_year_even_with_valid_page_text(pdf_catalog):  # noqa: F811
    root = pdf_catalog.root
    data, _, trace = search_annual_pdf_text(pdf_catalog, "lợi nhuận 2024", scope=resolve_scope("lợi nhuận 2024", "AAA"))
    pages = [p.model_dump(mode="json") for p in data.pages]
    with pytest.raises(ValueError, match="violates"):
        verify_selected(root, pages, question="lợi nhuận 2025", year="2025", trace=trace)
