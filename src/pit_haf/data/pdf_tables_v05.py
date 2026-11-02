"""Versioned currency-table candidates with implicit headers and wrapped row labels.

Legacy v0.4 extraction remains byte-replayable in pdf_tables.py. No OCR, merged
numeric cells, graph interpretation or semantic verification is performed here.
"""

import math
import re
from statistics import median

from pit_haf.data import pdf_tables as legacy
from pit_haf.data.snapshots import canonical
from pit_haf.llm.ollama import sha256

EXTRACTOR = "pdf_word_cells_v0.5"


def aligned(row, columns, tolerance):
    values = {}
    for word in row:
        if not legacy.NUMBER.fullmatch(word["text"]):
            continue
        matches = [c for c in columns if abs(c.get("anchor", c["x1"]) - word["x1"]) <= tolerance]
        if len(matches) == 1:
            values.setdefault(matches[0]["id"], []).append(word)
    return values


def complete(values, columns):
    return len(values) == len(columns) and all(len(v) == 1 for v in values.values())


def strip_index(label):
    while label and (label[0]["text"].rstrip(".").isdigit() or
                     (label[0]["text"].rstrip(".") and
                      all(c in "IVX" for c in label[0]["text"].rstrip(".")))):
        label = label[1:]
    return label


def label_cluster(row, lower, edge, width):
    """Use the alphabetic cluster nearest the values, excluding sidebars and note codes."""
    words = [w for w in row if lower <= w["x0"] and w["x1"] < edge - 2]
    clusters = [[]]
    for w in words:
        limit = max((w["bottom"] - w["top"]) * 3, width * .025)
        if clusters[-1] and w["x0"] - clusters[-1][-1]["x1"] > limit:
            clusters.append([])
        clusters[-1].append(w)
    usable = [p for p in clusters if any(any(c.isalpha() for c in w["text"]) and
              not re.fullmatch(r"\d+(?:\.\d+)?(?:\([a-z]\))?", w["text"]) for w in p)]
    return strip_index(usable[-1]) if usable else []


def column_anchors(rows, h, width, bottom):
    """Infer repeated numeric right edges below centered or right-aligned year headings."""
    cols = h["columns"]
    samples = {c["id"]: [] for c in cols}
    radius = min(b["x1"] - a["x1"] for a, b in zip(cols, cols[1:])) * .48
    for i, row in enumerate(rows):
        if not h["bottom"] < row[0]["top"] < bottom:
            continue
        for w in row:
            if not legacy.NUMBER.fullmatch(w["text"]):
                continue
            center = (w["x0"] + w["x1"]) / 2
            matches = [c for c in cols if abs(center - (c["x0"] + c["x1"]) / 2) < radius]
            if len(matches) == 1:
                samples[matches[0]["id"]].append((w["x1"], i))
    result = []
    for c in cols:
        values = samples[c["id"]]
        clusters = [(sum(abs(x - anchor) < 3 for x, _ in values), anchor) for anchor, _ in values]
        if not clusters:
            return []
        count, anchor = max(clusters)
        if len({i for x, i in values if abs(x - anchor) < 3}) < 3:
            return []
        if any(n == count and abs(other - anchor) > 6 for n, other in clusters):
            return []
        result.append({**c, "anchor": median(x for x, _ in values if abs(x - anchor) < 3)})
    return result


def header_groups(rows):
    groups = []
    for row in rows:
        years = [w for w in row if legacy.YEAR.fullmatch(w["text"])]
        if not 2 <= len(years) <= 12:
            continue
        cutoff = 2.5 * median(b["x1"] - a["x1"] for a, b in zip(years, years[1:]))
        parts = [[]]
        for year in years:
            if parts[-1] and year["x1"] - parts[-1][-1]["x1"] > cutoff:
                parts.append([])
            parts[-1].append(year)
        for cols in parts:
            values = [legacy.YEAR.fullmatch(w["text"])[1] for w in cols]
            if 2 <= len(cols) <= 8 and len(set(values)) == len(values):
                groups.append({"columns": cols, "top": min(w["top"] for w in cols),
                               "bottom": max(w["bottom"] for w in cols)})
    return groups


def bind_words(words, *, width, height, content_hash, page_number, unit_resolver=None, extractor=EXTRACTOR):
    if not 0 < width < 10000 or not 0 < height < 10000 or len(words) > 12000:
        raise ValueError("PDF page geometry/word budget exceeded")
    for i, w in enumerate(words):
        if (w["id"] != i or not isinstance(w["text"], str) or not w["text"].strip() or
                any(not math.isfinite(w[k]) for k in ("x0", "x1", "top", "bottom")) or
                not (0 <= w["x0"] < w["x1"] <= width + 1 and 0 <= w["top"] < w["bottom"] <= height + 1)):
            raise ValueError("Invalid/out-of-page word geometry")
    rows = legacy.word_rows(words)
    groups = header_groups(rows)
    headers = []
    skipped = []
    # Infer the label region only from repeated, complete numeric rows below the years.
    for h in groups:
        cols = h["columns"]
        h["tolerance"] = min(min(b["x1"] - a["x1"] for a, b in zip(cols, cols[1:])) * .25, width * .035)
        preceding = [g["columns"][-1]["x1"] for g in groups if abs(g["top"] - h["top"]) < height * .12
                     and g["columns"][-1]["x1"] < cols[0]["x0"]]
        lower = max(preceding, default=-10) + 5
        bottom = min((g["top"] for g in groups if g["top"] > h["bottom"] + 10 and
                      abs(g["columns"][0]["x1"] - cols[0]["x1"]) < h["tolerance"]), default=height)
        cols = column_anchors(rows, h, width, bottom)
        if not cols:
            continue
        h["columns"] = cols
        starts = []
        for row in rows:
            if not h["bottom"] < row[0]["top"] < bottom:
                continue
            values = aligned(row, cols, h["tolerance"])
            if not complete(values, cols):
                continue
            edge = min(v[0]["x0"] for v in values.values())
            label = label_cluster(row, lower, edge, width)
            if label and any(c.isalpha() for w in label for c in w["text"]):
                starts.append(label[0]["x0"])
        if len(starts) < 3:
            continue
        h.update(left=min(starts), lower=lower, bottom_limit=bottom, aligned_rows=len(starts))
        headers.append(h)
    cells, diagnostics = [], []
    for index, h in enumerate(headers):
        cols, tolerance = h["columns"], h["tolerance"]
        right = min((g["left"] - 10 for g in headers if abs(g["top"] - h["top"]) < height * .12 and
                     g["left"] > cols[-1]["x1"]), default=width)
        context_left = max(h["lower"], h["left"] - max(40, width * .025))
        context = [[w for w in row if context_left <= w["x0"] < right]
                   for row in rows if h["top"] - height * .20 <= row[0]["top"] <= h["bottom"] + 30]
        context = [r for r in context if r]
        if unit_resolver is None:
            units = legacy.phrase_refs(context, legacy.UNITS)
            unit_values = {u["value"] for u in units}
            units_by_column = {c["id"]: units[0] for c in cols} if len(unit_values) == 1 else {}
            unit_diagnostic = {}
        else:
            units_by_column, unit_diagnostic = unit_resolver(context, h, context_left, right)
            unit_values = {u["value"] for u in units_by_column.values()}
        scopes = legacy.phrase_refs(context, {"hop nhat": "consolidated", "rieng le": "parent"})
        scope_values = {s["value"] for s in scopes}
        diagnostic = {"header_index": index, "year_word_ids": [c["id"] for c in cols],
                      "aligned_rows": h["aligned_rows"], "unit_values": sorted(unit_values),
                      "scope_values": sorted(scope_values), "label_region_left": h["left"],
                      "numeric_column_right_edges": [c["anchor"] for c in cols]}
        diagnostic.update(unit_diagnostic)
        diagnostics.append(diagnostic)
        # An explicit currency qualifier is required even when the header has Chỉ tiêu.
        if len(unit_values) != 1 or any(c["id"] not in units_by_column for c in cols):
            diagnostic["stop_reason"] = "missing_or_ambiguous_currency_unit"
            continue
        scope = scopes[0] if len(scope_values) == 1 else None
        for row_index, row in enumerate(rows):
            if not h["bottom"] < row[0]["top"] < h["bottom_limit"]:
                continue
            local = [w for w in row if h["left"] - 10 <= w["x0"] < right]
            values = aligned(local, cols, tolerance)
            if not complete(values, cols):
                if values:
                    skipped.append({"header_index": index, "row_word_ids": [w["id"] for w in local],
                                    "reason": "incomplete_or_duplicate_column_alignment"})
                continue
            edge = min(v[0]["x0"] for v in values.values())
            label = label_cluster(local, h["left"] - 10, edge, width)
            if not label or not any(c.isalpha() for w in label for c in w["text"]):
                continue
            parts = [label]
            font_height = median(w["bottom"] - w["top"] for w in label)
            last_top = max(w["top"] for w in row)
            for following in rows[row_index + 1:row_index + 3]:
                following = [w for w in following if h["left"] - 10 <= w["x0"] < edge - 2]
                if not following or not 0 < following[0]["top"] - last_top < font_height * 1.7:
                    break
                # Lowercase indented continuation only; headings/notes stay separate.
                if (not following[0]["text"][0].islower() or
                        abs(following[0]["x0"] - label[0]["x0"]) > 3 * font_height):
                    break
                original_row = next(r for r in rows if following[0] in r)
                if aligned(original_row, cols, tolerance):
                    break
                parts.append(following)
                last_top = max(w["top"] for w in following)
            label_words = [w for part in parts for w in part]
            for col in cols:
                value = values[col["id"]][0]
                reasons = [] if scope else ["missing_or_ambiguous_statement_scope"]
                if len(parts) > 1:
                    reasons.append("wrapped_label_requires_review")
                if value["text"] == "-":
                    reasons.append("dash_is_not_zero")
                if any("/" in w["text"] for w in label_words):
                    reasons.append("row_specific_unit_or_ratio_requires_review")
                fields = {"label": legacy.locator(label_words), "label_parts": [legacy.locator(p) for p in parts],
                          "value": legacy.locator([value]), "period": legacy.locator([col]),
                          "unit": units_by_column[col["id"]], "statement_scope": scope}
                identity = {"extractor": extractor, "content_hash": content_hash, "page": page_number,
                            "header_index": index, "fields": fields}
                cells.append({"cell_id": sha256(canonical(identity)), **identity,
                              "year": legacy.YEAR.fullmatch(col["text"])[1], "review_reasons": reasons,
                              "structural_status": "needs_review" if reasons else "linked_candidate",
                              "semantic_support": "not_assessed", "human_reviewed": False})
    return {"extractor": extractor, "pdfplumber_version": legacy.pdfplumber.__version__,
            "content_hash": content_hash, "page": page_number, "width": width, "height": height,
            "coordinate_system": "PDF points; top-left origin; word boxes, not character offsets",
            "words": words, "header_diagnostics": diagnostics, "skipped_rows": skipped, "cells": cells}


def extract_page(payload, content_hash, page_number):
    raw = legacy.extract_page(payload, content_hash, page_number)
    result = bind_words(raw["words"], width=raw["width"], height=raw["height"],
                        content_hash=content_hash, page_number=page_number)
    result["excluded_outside_or_rotated_words"] = raw["excluded_outside_or_rotated_words"]
    return result


def replay_page(bundle, payload):
    if extract_page(payload, bundle["content_hash"], bundle["page"]) != bundle:
        raise ValueError("Table v0.5 bundle differs from raw PDF extraction")
    return True
