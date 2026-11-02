"""Synthetic OCR table layouts; no real-document labels or human reviews are created."""

from copy import deepcopy

import pytest

from pit_haf.data.ocr_cells import POLICY, link_page

SOURCE = {"version_id": "synthetic", "content_hash": "a" * 64, "reporting_period": "2024", "statement_scope": "consolidated"}


def fixture_page(*, headers=True, relative=False, rows=3):
    words = []

    def add(text, box, line, confidence=95):
        words.append({"id": f"W{len(words) + 1}", "text": text, "bbox_pixels": box, "confidence": confidence,
                      "reading_order": {"block_num": 1, "par_num": 1, "line_num": line, "word_num": len(words) + 1}})

    if headers:
        add("Hợp", [50, 100, 80, 116], 1)
        add("nhất", [85, 100, 120, 116], 1)
        add("triệu", [650, 130, 690, 146], 2)
        add("đồng", [695, 130, 730, 146], 2)
        add("Chỉ", [50, 160, 70, 176], 3)
        add("tiêu", [75, 160, 105, 176], 3)
        if relative:
            add("Năm", [410, 160, 440, 176], 3)
            add("nay", [445, 160, 470, 176], 3)
            add("Năm", [610, 160, 640, 176], 3)
            add("trước", [645, 160, 680, 176], 3)
        else:
            add("2024", [430, 160, 475, 176], 3)
            add("2023", [630, 160, 675, 176], 3)
    for i in range(rows):
        y = 250 + i * 12
        add("Doanh", [50, y, 90, y + 10], 4 + i)
        add("thu", [95, y, 125, y + 10], 4 + i)
        add(f"{i+1}.234.500", [400, y, 500, y + 10], 4 + i)
        add(f"({i+2}.345.600)", [600, y, 700, y + 10], 4 + i)
    return {"page": 1, "status": "ocr_unreviewed", "words": words,
            "geometry": {"image_width": 1000, "image_height": 1000}}


def test_literal_fields_link_to_their_own_column_with_unit_scope_and_explicit_year():
    result = link_page(fixture_page(), POLICY, SOURCE)
    assert len(result["cells"]) == 6
    current, prior = result["cells"][:2]
    assert current["fields"]["label"]["text"] == "Doanh thu"
    assert current["fields"]["value"]["text"] == "1.234.500"
    assert prior["fields"]["value"]["text"] == "(2.345.600)"
    assert (current["observed_year"], prior["observed_year"]) == (2024, 2023)
    assert current["fields"]["unit"]["text"] == "triệu đồng"
    assert current["fields"]["statement_scope"]["observed_value"] == "consolidated"
    assert current["fields"]["label"]["word_boxes"] == [[50, 250, 90, 260], [95, 250, 125, 260]]
    assert all(c["resolved_year"] is None and not c["automatic_fact"] and not c["human_reviewed"] for c in result["cells"])


def test_relative_headers_do_not_use_metadata_to_infer_absolute_years():
    page = fixture_page(relative=True)
    result = link_page(page, POLICY, SOURCE)
    assert [c["fields"]["period"]["observed_value"] for c in result["cells"][:2]] == ["relative_current", "relative_previous"]
    assert all(c["observed_year"] is None and "absolute_year_unresolved" in c["review_reasons"] for c in result["cells"])
    assert link_page(page, POLICY, {**SOURCE, "reporting_period": "1999"}) == result


def test_absent_headers_remain_visible_as_missing_even_when_source_has_metadata():
    result = link_page(fixture_page(headers=False), POLICY, SOURCE)
    assert len(result["cells"]) == 6
    assert all(c["fields"]["period"] is None and c["fields"]["unit"] is None and
               c["fields"]["statement_scope"] is None for c in result["cells"])
    assert "missing_or_ambiguous_statement_scope" in result["cells"][0]["review_reasons"]


@pytest.mark.parametrize("field", ["unit", "scope", "period"])
def test_conflicting_or_duplicate_header_refs_fail_closed(field):
    page = fixture_page()
    if field == "unit":
        target = next(w for w in page["words"] if w["text"] == "2023")
        target["text"], target["bbox_pixels"] = "VND", [650, 180, 700, 196]
    if field == "scope":
        row = [w for w in page["words"] if w["text"] in ("2023", "2024")]
        for w, text in zip(row, ["riêng", "lẻ"]):
            w["text"] = text
        row[1]["bbox_pixels"] = [480, 160, 510, 176]
    if field == "period":
        next(w for w in page["words"] if w["text"] == "2023")["text"] = "2024"
    result = link_page(page, POLICY, SOURCE)
    name = "statement_scope" if field == "scope" else field
    assert all(c["fields"][name] is None for c in result["cells"])


def test_low_confidence_label_and_dash_do_not_become_approved_zero_or_fixed_text():
    page = fixture_page(rows=4)
    page["words"][-2]["text"] = "-"
    page["words"][-4]["text"] = "D0anh"
    page["words"][-4]["confidence"] = 22
    cell = link_page(page, POLICY, SOURCE)["cells"][-2]
    assert cell["fields"]["label"]["text"] == "D0anh thu" and cell["fields"]["value"]["text"] == "-"
    assert {"low_confidence_field", "dash_is_not_zero"} <= set(cell["review_reasons"])


def test_fragmented_numbers_are_not_repaired_into_a_cell_value():
    page = fixture_page(rows=4)
    page["words"][-2]["text"] = "(4. 234.500)"
    result = link_page(page, POLICY, SOURCE)
    assert len(result["cells"]) == 7
    assert all(c["fields"]["value"]["text"] != "(4.234.500)" for c in result["cells"])
    assert "incomplete_numeric_row" in result["cells"][-1]["review_reasons"]


def test_duplicate_values_on_one_line_are_kept_in_diagnostics_and_not_guessed():
    page = fixture_page(rows=4)
    extra = deepcopy(page["words"][-2])
    extra["id"] = "W999"
    extra["text"] = "777.888"
    page["words"].append(extra)
    result = link_page(page, POLICY, SOURCE)
    assert len(result["cells"]) == 6
    assert any(d["reason"] == "duplicate_values_in_column_line" for d in result["diagnostics"])


def test_wrapped_label_is_not_automatically_joined_across_reading_lines():
    page = fixture_page()
    extra = deepcopy(page["words"][-4])
    extra.update(id="W999", text="đặc biệt", bbox_pixels=[50, 290, 130, 300],
                 reading_order={"block_num": 1, "par_num": 1, "line_num": 99, "word_num": 1})
    page["words"].append(extra)
    result = link_page(page, POLICY, SOURCE)
    assert all(c["fields"]["label"]["text"] == "Doanh thu" for c in result["cells"])
    assert all("same_line_label_may_be_incomplete" in c["review_reasons"] for c in result["cells"])


def test_missing_label_is_retained_without_borrowing_from_another_row():
    page = fixture_page()
    page["words"][-4]["text"] = "1"
    page["words"][-3]["text"] = "2"
    assert link_page(page, POLICY, SOURCE)["cells"][-1]["fields"]["label"] is None


def test_budget_and_column_gates_never_silently_return_a_truncated_table():
    result = link_page(fixture_page(rows=61), POLICY, SOURCE)
    assert result["cells"] == [] and result["diagnostics"][-1] == {"reason": "cell_budget_exceeded", "count": 122}
    result = link_page(fixture_page(rows=2), POLICY, SOURCE)
    assert result["cells"] == [] and result["diagnostics"] == [{"reason": "missing_or_ambiguous_numeric_columns"}]


def test_candidate_identity_is_bound_to_pdf_version_and_page():
    page = fixture_page()
    first = link_page(page, POLICY, SOURCE)["cells"][0]
    second = link_page(page, POLICY, {**SOURCE, "version_id": "another"})["cells"][0]
    assert first["candidate_id"] != second["candidate_id"]
    assert first["fields"] == second["fields"]


@pytest.mark.parametrize("change", ["single_year", "no_table_prefix", "two_period_rows"])
def test_navigation_years_or_ambiguous_header_rows_are_not_bound_as_cell_years(change):
    page = fixture_page()
    if change == "single_year":
        next(w for w in page["words"] if w["text"] == "2023")["text"] = "KẾT QUẢ"
    if change == "no_table_prefix":
        next(w for w in page["words"] if w["text"] == "Chỉ")["text"] = "KINH"
        next(w for w in page["words"] if w["text"] == "tiêu")["text"] = "DOANH"
    if change == "two_period_rows":
        for w in deepcopy([w for w in page["words"] if w["reading_order"]["line_num"] == 3]):
            w["id"] += "copy"
            w["reading_order"]["line_num"] = 99
            w["bbox_pixels"][1] += 30
            w["bbox_pixels"][3] += 30
            page["words"].append(w)
    result = link_page(page, POLICY, SOURCE)
    assert all(c["fields"]["period"] is None and c["observed_year"] is None for c in result["cells"])


def test_one_valid_numeric_fragment_cannot_stand_for_a_multi_token_ocr_number():
    page = fixture_page(rows=4)
    page["words"][-2]["text"] = "500"
    extra = deepcopy(page["words"][-2])
    extra.update(id="W999", text="4.234.", bbox_pixels=[400, 286, 450, 296])
    page["words"].append(extra)
    result = link_page(page, POLICY, SOURCE)
    assert len(result["cells"]) == 7
    assert all(c["fields"]["value"]["text"] != "500" for c in result["cells"])
    assert any(d["reason"] == "fragmented_or_extra_column_tokens" for d in result["diagnostics"])
