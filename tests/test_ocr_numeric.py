"""Synthetic literal checks, never a financial or human-gold benchmark."""

from copy import deepcopy

import pytest

from pit_haf.research.ocr_numeric import compare, validate_references


def fixture_data():
    refs = {"provenance": "assistant_visual_transcription", "independent_gold": False,
            "human_confirmed": False, "allowed_use": "development_diagnostic_only",
            "version_id": "test-source", "content_hash": "a" * 64, "page": 2,
            "cells": [{"id": "A", "bbox_normalized": [.1, .1, .4, .3], "literal": "(1.234)",
                       "column_label": "Năm nay", "resolved_year": None},
                      {"id": "B", "bbox_normalized": [.5, .1, .8, .3], "literal": "-",
                       "column_label": "Năm trước", "resolved_year": None}]}
    view = {"run": {"run_id": "synthetic", "profile_id": "pdf_ocr_region_v0.2"},
            "source": {"version_id": "test-source", "content_hash": "a" * 64},
            "pages": [{"page": 2, "status": "ocr_unreviewed",
                       "geometry": {"image_width": 1000, "image_height": 1000},
                       "words": []}]}
    return refs, view


def word(text, x, *, y=150, number=1):
    return {"id": f"W{number}", "text": text, "bbox_pixels": [x, y, x + 35, y + 20],
            "reading_order": {"block_num": 1, "par_num": 1, "line_num": 1}}


def test_literal_comparison_uses_own_column_and_keeps_relative_year_unresolved():
    refs, view = fixture_data()
    view["pages"][0]["words"] = [word("(1.234)", 150), word("-", 550, number=2), word("2024", 820, number=3)]
    result = compare(view, refs)
    assert result["literal_matches"] == result["whitespace_only_matches"] == 2
    assert result["cells"][0]["word_ids"] == ["W1"]
    assert result["cells"][1]["issues"] == ["dash_is_not_zero"]
    assert result["semantic_accuracy"] is None and result["independent_gold"] is False
    assert all(c["resolved_year"] is None for c in result["cells"])


@pytest.mark.parametrize("text,issue", [("1.234", "punctuation_or_sign_mismatch"),
                                       ("(1,234)", "punctuation_or_sign_mismatch"),
                                       ("(1.284)", "value_mismatch"),
                                       ("(1.234", "unbalanced_parentheses"),
                                       ("(I.234)", "non_numeric_characters")])
def test_sign_punctuation_and_digit_errors_are_never_silently_repaired(text, issue):
    refs, view = fixture_data()
    view["pages"][0]["words"] = [word(text, 150), word("0", 550, number=2)]
    result = compare(view, refs)
    assert result["literal_matches"] == result["whitespace_only_matches"] == 0
    assert result["cells"][0]["observed"] == text and issue in result["cells"][0]["issues"]
    assert result["cells"][1]["observed"] == "0"  # a dash is not zero


def test_fragmented_numbers_only_match_when_whitespace_alone_differs():
    refs, view = fixture_data()
    view["pages"][0]["words"] = [word("(1.", 150), word("234)", 200, number=2)]
    result = compare(view, refs)
    assert result["literal_matches"] == 0 and result["whitespace_only_matches"] == 1
    assert result["cells"][0]["observed"] == "(1. 234)"
    assert result["cells"][0]["issues"] == ["fragmented_tokens"]
    assert "missing_value" in result["cells"][1]["issues"]


@pytest.mark.parametrize("change", ["hash", "version", "page", "failed"])
def test_other_sources_or_failed_pages_are_rejected(change):
    refs, view = fixture_data()
    if change in ("hash", "version"):
        view["source"]["content_hash" if change == "hash" else "version_id"] = "wrong"
    else:
        view["pages"][0]["page" if change == "page" else "status"] = 3 if change == "page" else "failed"
    with pytest.raises(ValueError, match="differs|missing or failed"):
        compare(view, refs)


@pytest.mark.parametrize("change", ["gold", "human", "provenance", "year", "duplicate", "unbalanced", "boolean_box"])
def test_assistant_reference_contract_cannot_be_claimed_as_human_gold(change):
    refs, _ = fixture_data()
    if change in ("gold", "human", "provenance"):
        refs[{"gold": "independent_gold", "human": "human_confirmed", "provenance": "provenance"}[change]] = True
    if change == "year":
        refs["cells"][0]["resolved_year"] = 2024
    if change == "duplicate":
        refs["cells"].append(deepcopy(refs["cells"][0]))
    if change == "unbalanced":
        refs["cells"][0]["literal"] = "(123"
    if change == "boolean_box":
        refs["cells"][0]["bbox_normalized"][0] = False
    with pytest.raises(ValueError):
        validate_references(refs)
