"""Spatial/header OCR regression cases; all data and labels here are synthetic."""

from copy import deepcopy

import pytest
from test_ocr_cells import SOURCE, fixture_page

from pit_haf.data import ocr_cells_v02 as spatial


def page_fixture(**kwargs):
    page = fixture_page(**kwargs)
    page["image_sha256"] = "b" * 64
    page["geometry"].update(dpi=240, rotation=0)
    for i, word in enumerate(page["words"]):
        word["reading_order"] = {"block_num": i + 1, "par_num": 1, "line_num": 1, "word_num": 1}
        if word["bbox_pixels"][1] >= 250:
            offset = ((word["bbox_pixels"][1] - 250) // 12) * 68
            word["bbox_pixels"][1] += offset
            word["bbox_pixels"][3] += offset
    return page


def link(page):
    return spatial.link_page(page, spatial.POLICY, SOURCE)


def header_fixture(body):
    header = deepcopy(body)
    header["words"] = [deepcopy(w) for w in fixture_page(relative=True)["words"] if 160 <= w["bbox_pixels"][1] <= 176]
    header["geometry"].update(ocr_region_normalized=[0, .14, 1, .18], ocr_crop_pixels=[0, 140, 1000, 180])
    return header


def test_spatial_rows_reconstruct_headers_without_trusting_sparse_native_reading_order():
    page = page_fixture(relative=True)
    result = link(page)
    assert len(result["cells"]) == 6
    assert [c["fields"]["period"]["observed_value"] for c in result["cells"][:2]] == ["relative_current", "relative_previous"]
    assert all(c["resolved_year"] is None and c["observed_year"] is None for c in result["cells"])


def test_wrapped_lowercase_continuation_keeps_each_word_box_and_does_not_repair_text():
    page = page_fixture()
    sample = deepcopy(page["words"][-1])
    sample.update(id="extra", text="thuầnn", bbox_pixels=[50, 270, 100, 280])
    page["words"].append(sample)
    result = link(page)
    first = result["cells"][0]
    assert first["fields"]["label"]["text"] == "Doanh thu thuầnn"
    assert len(first["label_parts"]) == 2
    assert first["label_parts"][1]["word_ids"] == ["extra"]
    assert "wrapped_label_requires_review" in first["review_reasons"]
    assert result["cells"][2]["fields"]["label"]["text"] == "Doanh thu"


def test_another_capitalized_label_is_ambiguous_and_never_borrowed_into_wrapped_text():
    page = page_fixture()
    extra = deepcopy(page["words"][-1])
    extra.update(id="extra", text="Chi phí", bbox_pixels=[50, 270, 100, 280])
    page["words"].append(extra)
    assert link(page)["cells"][0]["fields"]["label"] is None


def test_annual_statement_period_is_separate_from_relative_columns_and_document_metadata():
    page = page_fixture(relative=True)
    extra = deepcopy(page["words"][-1])
    extra.update(id="annual", text="cho năm tài chính kết thúc ngày 31 tháng 12 năm 2024", bbox_pixels=[50, 190, 700, 205])
    page["words"].append(extra)
    result = link(page)
    for cell in result["cells"]:
        assert cell["fields"]["statement_period"]["observed_end_date"] == "2024-12-31"
        assert cell["observed_statement_year"] == 2024
        assert cell["observed_year"] is None and cell["resolved_year"] is None
    other = spatial.link_page(page, spatial.POLICY, {**SOURCE, "reporting_period": "1999"})
    assert other == result


@pytest.mark.parametrize("text", ["BÁO CÁO THƯỜNG NIÊN 2024", "cho quý kết thúc ngày 31 tháng 12 năm 2024",
                                 "cho năm tài chính kết thúc ngày 30 tháng 2 năm 2024"])
def test_footer_quarter_and_invalid_dates_are_not_annual_statement_evidence(text):
    page = page_fixture()
    page["words"].append({**deepcopy(page["words"][-1]), "id": "annual", "text": text, "bbox_pixels": [50, 190, 700, 205]})
    assert all(c["fields"]["statement_period"] is None for c in link(page)["cells"])


def test_duplicate_annual_periods_stay_ambiguous():
    page = page_fixture()
    for i in range(2):
        page["words"].append({**deepcopy(page["words"][-1]), "id": f"annual{i}",
                             "text": "cho năm tài chính kết thúc ngày 31 tháng 12 năm 2024",
                             "bbox_pixels": [50, 190 + 25 * i, 700, 205 + 25 * i]})
    assert all(c["fields"]["statement_period"] is None for c in link(page)["cells"])


def test_accent_folding_cannot_turn_hoat_dong_into_a_currency_unit():
    page = page_fixture()
    page["words"].append({**deepcopy(page["words"][-1]), "id": "homograph", "text": "ĐỘNG", "bbox_pixels": [50, 210, 100, 225]})
    result = link(page)
    assert all(c["fields"]["unit"]["text"] == "triệu đồng" for c in result["cells"])
    assert any(d["reason"] == "non_currency_homograph_rejected" for d in result["diagnostics"])


def test_header_supplement_preserves_numeric_body_and_every_original_word_reference():
    body = page_fixture()
    header = header_fixture(body)
    merged, origins, diagnostic = spatial.supplement_page(body, header, body_run_id="body", header_run_id="header", policy=spatial.POLICY)
    result = spatial.link_page(merged, spatial.POLICY, SOURCE, origins=origins)
    assert [c["fields"]["value"]["text"] for c in result["cells"]] == [c["fields"]["value"]["text"] for c in link(body)["cells"]]
    assert result["cells"][0]["fields"]["period"]["text"] == "Năm nay"
    assert result["cells"][0]["fields"]["period"]["word_refs"][0]["ocr_run_id"] == "header"
    assert result["cells"][0]["fields"]["value"]["word_refs"][0]["ocr_run_id"] == "body"
    assert len(diagnostic["superseded_body_words"]) == 4
    assert any(w["text"] == "2024" for w in body["words"])  # inputs were never changed


@pytest.mark.parametrize("change", ["page", "image", "dpi", "failed", "no_region", "large_region", "body_overlap", "missing_column"])
def test_header_supplement_rejects_other_pages_geometry_or_numeric_overwrites(change):
    body = page_fixture()
    header = header_fixture(body)
    if change == "page":
        header["page"] = 2
    if change == "image":
        header["image_sha256"] = "c" * 64
    if change == "dpi":
        header["geometry"]["dpi"] = 180
    if change == "failed":
        header["status"] = "failed"
    if change == "no_region":
        del header["geometry"]["ocr_region_normalized"]
    if change == "large_region":
        header["geometry"]["ocr_region_normalized"] = [0, 0, 1, .2]
    if change == "body_overlap":
        header["geometry"].update(ocr_region_normalized=[0, .24, 1, .26], ocr_crop_pixels=[0, 240, 1000, 260])
    if change == "missing_column":
        header["geometry"].update(ocr_region_normalized=[0, .14, .5, .18], ocr_crop_pixels=[0, 140, 500, 180])
    with pytest.raises(ValueError):
        spatial.supplement_page(body, header, body_run_id="body", header_run_id="header", policy=spatial.POLICY)
