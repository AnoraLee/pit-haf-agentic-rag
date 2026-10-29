"""Synthetic layout variation tests; no real financial answers are used as gold."""

import copy

from pit_haf.data import pdf_tables as legacy
from pit_haf.data import pdf_tables_v05 as new


def fixture(centered=False, unit=True, wrapped=False, sidebar=False):
    rows = [(20, [("Hop", 40, 60), ("nhat", 62, 85)]),
            (60, [("2024", 280, 300), ("2023", 380, 400)])]
    if unit:
        rows.append((40, [("Trieu", 40, 65), ("VND", 67, 90)]))
    for i, label in enumerate(("Loi nhuan", "Doanh thu", "Tien mat")):
        y = 90 + i * 40
        parts = [(label, 60, 130), ("(12)", 280 + 25 * centered, 300 + 25 * centered),
                 ("25", 380 + 25 * centered, 400 + 25 * centered)]
        if sidebar:
            parts.insert(0, ("UNRELATED SIDEBAR", 0, 20))
        rows.append((y, parts))
        if i == 0 and wrapped:
            rows.append((y + 12, [("sau thue", 60, 110)]))
    words = []
    for top, parts in rows:
        for text, x0, x1 in parts:
            words.append({"id": len(words), "text": text, "x0": x0, "x1": x1, "top": top, "bottom": top + 10})
    return words


def bind(words):
    return new.bind_words(words, width=600, height=800, content_hash="a" * 64, page_number=1)


def test_implicit_centered_headers_use_repeated_numeric_edges_and_keep_signs():
    b = bind(fixture(centered=True))
    assert len(b["cells"]) == 6
    c = b["cells"][0]
    assert c["fields"]["value"]["text"] == "(12)" and c["year"] == "2024"
    assert c["fields"]["period"]["bbox"][2] == 300
    assert b["header_diagnostics"][0]["numeric_column_right_edges"] == [325, 425]
    assert not c["human_reviewed"] and c["semantic_support"] == "not_assessed"


def test_wrapped_labels_keep_each_part_and_exclude_sidebar():
    b = bind(fixture(wrapped=True, sidebar=True))
    c = b["cells"][0]
    assert c["fields"]["label"]["text"] == "Loi nhuan sau thue"
    assert len(c["fields"]["label_parts"]) == 2
    assert "wrapped_label_requires_review" in c["review_reasons"]
    assert "SIDEBAR" not in str([c["fields"]["label"] for c in b["cells"]])


def test_chart_like_years_without_currency_or_repeated_rows_are_not_tables():
    assert not bind(fixture(unit=False))["cells"]
    words = fixture()
    assert not bind([w for w in words if w["top"] < 120])["cells"]
    b = bind(fixture(unit=False))
    assert b["header_diagnostics"][0]["stop_reason"] == "missing_or_ambiguous_currency_unit"


def test_two_staggered_tables_keep_their_own_currency_and_scope():
    left = fixture()
    right = copy.deepcopy(fixture())
    for w in right:
        w["id"] += len(left)
        w["x0"] += 650
        w["x1"] += 650
        w["top"] += 20
        w["bottom"] += 20
    b = new.bind_words(left + right, width=1300, height=800, content_hash="a" * 64, page_number=1)
    assert len(b["cells"]) == 12 and len(b["header_diagnostics"]) == 2
    for c in b["cells"]:
        unit = c["fields"]["unit"]["source"]["bbox"]
        assert (unit[0] > 650) == (c["header_index"] == 1)


def test_legacy_header_requirement_and_byte_shape_remain_unchanged():
    words = fixture()
    b = legacy.bind_words(words, width=600, height=800, content_hash="a" * 64, page_number=1)
    assert b["extractor"] == "pdf_word_cells_v0.4" and not b["cells"]
