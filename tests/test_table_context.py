"""Generic label, duplicate and conflict checks using deliberately synthetic cells."""

import copy
import json
from pathlib import Path

import pytest

from pit_haf.research.table_context import build_context, load_policy, relevance
from pit_haf.research.table_evidence import ShortCellSelection, verify_contextual_selection


@pytest.fixture
def policy():
    return load_policy(Path(__file__).resolve().parents[1])


def bundle(labels_values, *, version="v1", scope="consolidated", unit="triệu VND", year="2024"):
    def part(text):
        return {"text": text, "word_ids": [1], "bbox": [10, 10, 20, 20]}
    cells = []
    for i, (label, value) in enumerate(labels_values):
        cells.append({"cell_id": f"cell-{i}", "page": i + 1, "year": year,
                      "fields": {"label": part(label), "value": part(value),
                                 "unit": {"value": unit, "source": part(unit)} if unit else None,
                                 "statement_scope": {"value": scope, "source": part(scope)} if scope else None},
                      "review_reasons": []})
    return {"source": {"version_id": version, "ticker": "SYN"}, "table": {"cells": cells}}


@pytest.mark.parametrize("query,label,expected", [
    ("Kết quả lợi nhuận 2024 được mô tả thế nào?", "Các cam kết ngoại bảng", False),
    ("Lợi nhuận 2024", "Lợi ích của cổ đông không kiểm soát", False),
    ("Lợi nhuận 2024", "Lợi nhuận sau thuế", True),
    ("Lợi nhuận sau thuế 2024", "Lợi nhuận thuần từ hoạt động kinh doanh trước chi phí dự phòng", False),
    ("LNST 2024", "Lợi nhuận sau thuế thuộc cổ đông công ty mẹ", False),
    ("LNTT 2024", "Lợi nhuận trước thuế và lãi vay", False),
    ("EBITDA 2024", "Lợi nhuận trước thuế, lãi vay và khấu hao", True),
    ("Lợi nhuận cổ đông công ty mẹ 2024", "Lợi nhuận sau thuế", False),
    ("Lợi nhuận sau thuế 2024", "Lợi nhuận thuần", True),
    ("Thu nhập năm 2024", "Chi phí thuế thu nhập doanh nghiệp", False),
    ("Doanh thu 2024", "Doanh thu thuần", True),
    ("Dòng tiền năm 2024", "Tiền thuần từ hoạt động kinh doanh", True),
    ("Dòng tiền năm 2024", "Lưu chuyển tiền thuần từ/(sử dụng vào) hoạt động kinh doanh", True),
    ("Tài sản năm 2024", "Nợ phải trả", True),
    ("Kế hoạch lợi nhuận năm 2024", "Lợi nhuận trước thuế", False),
    ("Tăng trưởng lợi nhuận năm 2024", "Lợi nhuận sau thuế", False),
    ("Lợi nhuận năm 2024", "Biên lợi nhuận sau thuế", False),
    ("Lợi nhuận năm 2024", "Lợi nhuận sau thuế/Doanh thu thuần", False),
    ("Công ty phát triển thế nào năm 2024?", "Lợi nhuận sau thuế", False),
])
def test_complete_financial_phrases_replace_incidental_question_tokens(policy, query, label, expected):
    assert relevance(query, label, policy)[0] is expected


def test_grouping_keeps_every_source_reference_and_never_changes_input(policy):
    b = bundle([("Lợi nhuận thuần", "(12)"), ("LỢI NHUẬN THUẦN", "(12)")])
    before = copy.deepcopy(b)
    context, audit = build_context([b], query="lợi nhuận năm 2024", year="2024", policy=policy)
    assert b == before and len(context) == 1
    assert context[0]["equivalent_count"] == 2
    assert {c["page"] for c in context[0]["equivalent_candidates"]} == {1, 2}
    assert context[0]["value"] == "(12)" and audit["grouped_duplicate_cells"] == 1
    assert not context[0]["human_reviewed"]


@pytest.mark.parametrize("values", [("12", "(12)"), ("1.000", "1,000")])
def test_conflicting_numeric_tokens_are_not_merged_or_chosen_by_model(policy, values):
    b = bundle([("Lợi nhuận sau thuế", value) for value in values])
    context, audit = build_context([b], query="lợi nhuận 2024", year="2024", policy=policy)
    assert len(context) == 2 and len(audit["conflict_groups"]) == 1
    draft = ShortCellSelection(selected_cell_ids=["C1", "C2"], insufficient_evidence=False, missing_information=[])
    picked, blocked = verify_contextual_selection(draft, context, True)
    assert not picked and len(blocked) == 2
    assert all(c["reasons"] == ["conflicting_values_same_label_requires_review"] for c in blocked)


def test_unknown_scope_versions_units_and_parent_entities_are_kept_separate(policy):
    b = bundle([("Lợi nhuận sau thuế", "12"), ("Lợi nhuận sau thuế", "12")], scope=None)
    c, a = build_context([b], query="lợi nhuận 2024", year="2024", policy=policy)
    assert len(c) == 2 and not a["duplicate_groups"]
    bs = [bundle([("Lợi nhuận sau thuế", "12")], version="v1"),
          bundle([("Lợi nhuận sau thuế", "12")], version="v2"),
          bundle([("Lợi nhuận sau thuế", "12")], version="v1", scope="parent"),
          bundle([("Lợi nhuận sau thuế", "12")], version="v1", unit="tỷ VNĐ")]
    # Real IDs differ when their geometry/qualifiers differ; keep the synthetic IDs unique too.
    for i, item in enumerate(bs):
        item["table"]["cells"][0]["cell_id"] = str(i)
    c, a = build_context(bs, query="lợi nhuận 2024", year="2024", policy=policy)
    assert len(c) == 4 and not a["duplicate_groups"] and not a["conflict_groups"]


def test_year_bounds_and_context_budget_keep_whole_cells(policy):
    bs = [bundle([("Lợi nhuận sau thuế", "12")], version=str(i)) for i in range(25)]
    c, a = build_context(bs, query="lợi nhuận 2024", year="2024", policy=policy, max_cells=18, max_characters=2500)
    assert 0 < len(c) < 18 and len(json.dumps(c, ensure_ascii=False)) <= 2500
    assert a["budget_excluded"]
    assert not build_context(bs, query="lợi nhuận 2025", year="2025", policy=policy)[0]
