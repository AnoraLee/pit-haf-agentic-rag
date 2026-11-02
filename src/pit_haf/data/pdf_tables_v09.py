"""Versioned unit locators for plain VND year columns; values stay literal/unreviewed."""

import json
import re
from statistics import median

from pit_haf.data import pdf_tables as legacy
from pit_haf.data import pdf_tables_v05 as layout
from pit_haf.data.financial_sections import normalized

EXTRACTOR = "pdf_word_cells_v0.9"
POLICY = "configs/table_units_v0_9.json"
RULES = {"policy_id": "table_currency_units_v0.9", "status": "development_not_frozen",
         "header_band_font_heights": 2.5, "declaration_above_font_heights": 4,
         "column_center_font_heights": 2, "column_gap_fraction": 0.25,
         "plain_currency_tokens": ["vnd", "dong"], "canonical_plain_unit": "VND",
         "require_all_columns": True, "allow_numeric_rescaling": False}


def load_policy(root):
    data = json.loads((root / POLICY).read_text(encoding="utf-8"))
    if data != RULES:
        raise ValueError("Unknown table currency unit policy/budget")
    return data


def unit_ref(value, words, basis):
    return {"value": value, "source": legacy.locator(words), "binding_basis": basis}


def resolve_units(context, header, left, right):
    """Keep scaled phrases; bare VND needs aligned per-year tokens or an explicit declaration.

    A currency in prose, a neighbouring panel or a later row is not a unit header.
    Mixed currencies/scales and partial/duplicate per-column qualifiers stop binding.
    """
    cols = header["columns"]
    font = median(c["bottom"] - c["top"] for c in cols)
    gap = min((b["x0"] + b["x1"] - a["x0"] - a["x1"]) / 2 for a, b in zip(cols, cols[1:]))
    tolerance = min(font * RULES["column_center_font_heights"], gap * RULES["column_gap_fraction"])
    scaled = legacy.phrase_refs(context, legacy.UNITS)
    scaled_values = {u["value"] for u in scaled}
    declarations, columns = [], {}
    column_error = None
    for row in context:
        # The context already excludes other table panels horizontally.
        local = [w for w in row if left <= w["x0"] and w["x1"] <= right]
        if not local:
            continue
        text = normalized(" ".join(w["text"] for w in local))
        if header["top"] - font * RULES["declaration_above_font_heights"] <= local[0]["top"] <= header["bottom"]:
            if text in {"don vi " + token for token in RULES["plain_currency_tokens"]}:
                declarations.append(unit_ref("VND", local, "explicit_unit_declaration"))
        if not header["bottom"] <= local[0]["top"] <= header["bottom"] + font * RULES["header_band_font_heights"]:
            continue
        # Scaled unit rows are handled by the legacy full phrases, never their bare VND suffix.
        if any(normalized(w["text"]) in {"trieu", "ty", "nghin", "ngan", "million", "billion"} for w in local):
            continue
        known = [w for w in local if normalized(w["text"]) in RULES["plain_currency_tokens"]]
        if not known:
            if any(re.fullmatch(r"[A-Z]{3}", w["text"]) and any(
                abs((w["x0"] + w["x1"] - c["x0"] - c["x1"]) / 2) <= tolerance for c in cols
            ) for w in local):
                column_error = "unsupported_column_currency"
            continue
        if any(normalized(w["text"]) not in RULES["plain_currency_tokens"] for w in local):
            column_error = "non_currency_text_in_column_unit_row"
            continue
        for word in known:
            center = (word["x0"] + word["x1"]) / 2
            matches = [c for c in cols if abs(center - (c["x0"] + c["x1"]) / 2) <= tolerance]
            if len(matches) != 1 or matches[0]["id"] in columns:
                column_error = "ambiguous_or_duplicate_column_unit"
                continue
            columns[matches[0]["id"]] = unit_ref("VND", [word], "aligned_year_column")
    diagnostic = {"unit_policy_id": RULES["policy_id"],
                  "column_unit_word_ids": {str(k): v["source"]["word_ids"] for k, v in columns.items()}}
    if columns and len(columns) != len(cols):
        column_error = "incomplete_column_unit_row"
    if column_error or (scaled_values and (columns or declarations)) or len(scaled_values) > 1:
        diagnostic["unit_binding_failure"] = column_error or "conflicting_unit_qualifiers"
        return {}, diagnostic
    if scaled_values:
        diagnostic["unit_binding_basis"] = "scaled_header_phrase"
        return {c["id"]: scaled[0] for c in cols}, diagnostic
    if columns:
        diagnostic["unit_binding_basis"] = "aligned_year_columns"
        return columns, diagnostic
    if len(declarations) == 1:
        diagnostic["unit_binding_basis"] = "explicit_unit_declaration"
        return {c["id"]: declarations[0] for c in cols}, diagnostic
    diagnostic["unit_binding_failure"] = "missing_or_ambiguous_explicit_unit"
    return {}, diagnostic


def bind_words(words, *, width, height, content_hash, page_number):
    return layout.bind_words(words, width=width, height=height, content_hash=content_hash,
                             page_number=page_number, unit_resolver=resolve_units, extractor=EXTRACTOR)


def extract_page(payload, content_hash, page_number):
    raw = legacy.extract_page(payload, content_hash, page_number)
    result = bind_words(raw["words"], width=raw["width"], height=raw["height"],
                        content_hash=content_hash, page_number=page_number)
    result["excluded_outside_or_rotated_words"] = raw["excluded_outside_or_rotated_words"]
    return result


def replay_page(bundle, payload):
    if extract_page(payload, bundle["content_hash"], bundle["page"]) != bundle:
        raise ValueError("Table v0.9 unit bundle differs from raw PDF extraction")
    return True
