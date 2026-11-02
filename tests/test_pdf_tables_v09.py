"""Synthetic currency binding and legacy compatibility, never real financial gold labels."""

import copy
from pathlib import Path

import pytest
from test_pdf_tables_v05 import fixture
from test_table_evidence import synthetic_pdf

from pit_haf.data import pdf_tables_v05 as previous
from pit_haf.data import pdf_tables_v09 as current
from pit_haf.llm.ollama import sha256


def column_fixture(tokens=("VND", "VND"), *, unit=False, top=76, shift=0):
    words = fixture(unit=unit)
    for i, text in enumerate(tokens):
        words.append({"id": len(words), "text": text, "x0": 280 + i * 100 + shift,
                      "x1": 300 + i * 100 + shift, "top": top, "bottom": top + 10})
    return words


def bind(words, *, width=600):
    return current.bind_words(words, width=width, height=800, content_hash="a" * 64, page_number=1)


@pytest.mark.parametrize("tokens", [("VND", "VND"), ("VNĐ", "VNĐ"), ("đồng", "đồng")])
def test_plain_units_have_distinct_source_boxes_for_each_year_and_keep_signs(tokens):
    words = column_fixture(tokens)
    result = bind(words)
    assert len(result["cells"]) == 6
    a, b = result["cells"][:2]
    assert a["year"] == "2024" and a["fields"]["value"]["text"] == "(12)"
    assert a["fields"]["unit"]["value"] == b["fields"]["unit"]["value"] == "VND"
    assert a["fields"]["unit"]["source"]["word_ids"] != b["fields"]["unit"]["source"]["word_ids"]
    assert a["fields"]["unit"]["binding_basis"] == "aligned_year_column"
    assert not a["human_reviewed"] and a["semantic_support"] == "not_assessed"
    assert not previous.bind_words(words, width=600, height=800, content_hash="a" * 64, page_number=1)["cells"]


@pytest.mark.parametrize("tokens", [("VND",), ("VND", "USD"), ("USD", "USD"), ("VND", "VND", "VND")])
def test_partial_unsupported_and_duplicate_currency_columns_are_not_guessed(tokens):
    result = bind(column_fixture(tokens))
    assert not result["cells"]
    assert result["header_diagnostics"][0]["unit_binding_failure"]


@pytest.mark.parametrize("change", ["below_table", "shifted", "body_prose", "mixed_scale"])
def test_currency_outside_headers_or_with_conflicting_scale_does_not_bind(change):
    words = column_fixture(top=300 if change == "below_table" else 76,
                           shift=50 if change == "shifted" else 0, unit=change == "mixed_scale")
    if change == "body_prose":
        words.append({"id": len(words), "text": "giao dich", "x0": 60, "x1": 130, "top": 76, "bottom": 86})
    assert not bind(words)["cells"]


def test_plain_shared_unit_needs_an_explicit_nearby_declaration():
    words = fixture(unit=False)
    for text, x0, x1 in [("Don", 40, 60), ("vi:", 62, 80), ("VNĐ", 82, 102)]:
        words.append({"id": len(words), "text": text, "x0": x0, "x1": x1, "top": 40, "bottom": 50})
    result = bind(words)
    assert len(result["cells"]) == 6
    assert result["cells"][0]["fields"]["unit"]["binding_basis"] == "explicit_unit_declaration"
    without_declaration = [w for w in words if w["text"] not in {"Don", "vi:"}]
    for i, word in enumerate(without_declaration):
        word["id"] = i
    assert not bind(without_declaration)["cells"]


def test_scaled_units_do_not_become_plain_vnd_and_old_layout_still_replays():
    words = fixture()
    before = copy.deepcopy(words)
    old = previous.bind_words(words, width=600, height=800, content_hash="a" * 64, page_number=1)
    new = bind(words)
    assert words == before
    assert [c["fields"] for c in new["cells"]] == [c["fields"] for c in old["cells"]]
    assert all(c["fields"]["unit"]["value"] == "triệu VND" for c in new["cells"])


def test_adjacent_tables_do_not_share_plain_currency_tokens():
    left = column_fixture()
    right = fixture(unit=False)
    for w in right:
        w["id"] += len(left)
        w["x0"] += 650
        w["x1"] += 650
    result = bind(left + right, width=1300)
    assert len(result["cells"]) == 6
    assert all(c["fields"]["value"]["bbox"][0] < 650 for c in result["cells"])
    assert result["header_diagnostics"][1]["stop_reason"] == "missing_or_ambiguous_currency_unit"


def test_plain_unit_raw_pdf_replay_rejects_forged_locator_even_if_hashes_are_recomputed():
    raw = synthetic_pdf(rows=3, unit=None, column_units=True)
    digest = sha256(raw)
    result = current.extract_page(raw, digest, 1)
    assert len(result["cells"]) == 6 and current.replay_page(result, raw)
    forged = copy.deepcopy(result)
    forged["cells"][0]["fields"]["unit"]["source"]["bbox"][0] += 1
    with pytest.raises(ValueError, match="differs from raw"):
        current.replay_page(forged, raw)


def test_policy_file_matches_the_versioned_rules():
    assert current.load_policy(Path(__file__).resolve().parents[1]) == current.RULES
