"""Experimental geometric table candidates, never independently reviewed financial facts.

Word boxes use pdfplumber's PDF points, top-left origin on the rendered page.
Field locators cite separate words; a reconstructed row is not a literal quote.
"""

import io
import math
import re
from statistics import median

import pdfplumber

from pit_haf.data.financial_sections import normalized
from pit_haf.data.snapshots import canonical
from pit_haf.llm.ollama import sha256

EXTRACTOR = "pdf_word_cells_v0.4"
YEAR = re.compile(r"(?:\d{1,2}[/.-]\d{1,2}[/.-])?((?:19|20)\d{2})$")
NUMBER = re.compile(r"(?:[+−-]?\d[\d.,]*|\(\d[\d.,]*\)|-)$")
UNITS = {"ty dong": "tỷ đồng", "ty vnd": "tỷ VNĐ", "trieu dong": "triệu đồng",
         "trieu vnd": "triệu VND", "nghin dong": "nghìn đồng"}


def word_rows(words):
    rows = []
    for word in sorted(words, key=lambda w: ((w["top"] + w["bottom"]) / 2, w["x0"], w["id"])):
        center = (word["top"] + word["bottom"]) / 2
        tolerance = max(2., min(6., (word["bottom"] - word["top"]) * .28))
        if rows and abs(center - median((w["top"] + w["bottom"]) / 2 for w in rows[-1])) <= tolerance:
            rows[-1].append(word)
        else:
            rows.append([word])
    return [sorted(row, key=lambda w: (w["x0"], w["id"])) for row in rows]


def locator(words):
    return {"text": " ".join(w["text"] for w in words), "word_ids": [w["id"] for w in words],
            "bbox": [min(w["x0"] for w in words), min(w["top"] for w in words),
                     max(w["x1"] for w in words), max(w["bottom"] for w in words)]}


def phrase_refs(rows, phrases):
    found = []
    for row in rows:
        for n in range(1, 4):
            for i in range(len(row) - n + 1):
                part = row[i:i + n]
                value = phrases.get(normalized(" ".join(w["text"] for w in part)))
                if value and all(b["x0"] - a["x1"] < 2 * (a["bottom"] - a["top"])
                                 for a, b in zip(part, part[1:])):
                    found.append({"value": value, "source": locator(part)})
    return found


def headers(rows):
    """Require multiple explicit years and a nearby column-label prefix, no year inference."""
    result = []
    for row in rows:
        years = [w for w in row if YEAR.fullmatch(w["text"])]
        if len(years) < 2:
            continue
        groups = [[]]
        gaps = [b["x1"] - a["x1"] for a, b in zip(years, years[1:])]
        split_gap = 2.5 * median(gaps)
        for year in years:
            if groups[-1] and year["x1"] - groups[-1][-1]["x1"] > split_gap:
                groups.append([])
            groups[-1].append(year)
        for group in groups:
            if len(group) < 2:
                continue
            # A repeated year can mean different entities/quarters; do not guess its meaning.
            values = [YEAR.fullmatch(w["text"])[1] for w in group]
            if len(set(values)) != len(values):
                continue
            prefixes = [w for w in row if w["x0"] < group[0]["x0"] and normalized(w["text"]) in {"stt", "chi"}]
            if not prefixes:
                continue
            start = max(prefixes, key=lambda w: w["x0"])["x0"]
            # Prefer STT when it immediately precedes Chỉ tiêu.
            starts = [w["x0"] for w in prefixes if normalized(w["text"]) == "stt" and 0 <= start - w["x0"] < 120]
            start = min(starts, default=start)
            result.append({"columns": group, "left": start, "top": min(w["top"] for w in group),
                           "bottom": max(w["bottom"] for w in group)})
    return result


def bind_words(words, *, width, height, content_hash, page_number):
    """Conservative currency-table binding; preserve candidates and missing qualifiers.

    Only separate numeric tokens aligned to explicit year headers are handled.
    Ratios, dates inside labels, merged cells and ambiguous columns are unsupported.
    """
    if not 0 < width < 10000 or not 0 < height < 10000 or len(words) > 12000:
        raise ValueError("PDF page dimensions/word budget exceeded")
    for i, w in enumerate(words):
        if (w["id"] != i or not isinstance(w["text"], str) or not w["text"].strip() or
                any(not math.isfinite(w[k]) for k in ("x0", "x1", "top", "bottom")) or
                not (0 <= w["x0"] < w["x1"] <= width + 1 and 0 <= w["top"] < w["bottom"] <= height + 1)):
            raise ValueError("Invalid/out-of-page word geometry")
    rows = word_rows(words)
    candidates, diagnostics, skipped = [], [], []
    all_headers = headers(rows)
    for header_index, h in enumerate(all_headers):
        cols = h["columns"]
        right = min((x["left"] for x in all_headers if x["left"] > h["left"] and
                     abs(x["top"] - h["top"]) < 10), default=width)
        bottom = min((x["top"] for x in all_headers if x["top"] > h["bottom"] and
                      abs(x["left"] - h["left"]) < 20), default=height)
        gap = min(b["x1"] - a["x1"] for a, b in zip(cols, cols[1:]))
        tolerance = min(gap * .25, width * .035)
        context = [[w for w in row if h["left"] - 5 <= w["x0"] < right]
                   for row in rows if h["top"] - height * .16 <= row[0]["top"] <= h["bottom"] + 25]
        context = [row for row in context if row]
        units = phrase_refs(context, UNITS)
        unit_values = {u["value"] for u in units}
        scopes = phrase_refs(context, {"hop nhat": "consolidated", "rieng le": "parent"})
        scope_values = {s["value"] for s in scopes}
        unit = units[0] if len(unit_values) == 1 else None
        scope = scopes[0] if len(scope_values) == 1 else None
        diagnostics.append({"header_index": header_index, "year_word_ids": [c["id"] for c in cols],
                            "unit_values": sorted(unit_values), "scope_values": sorted(scope_values)})
        for row in rows:
            if not h["bottom"] < row[0]["top"] < bottom:
                continue
            local = [w for w in row if h["left"] - 5 <= w["x0"] < right]
            cells = {}
            for w in local:
                if not NUMBER.fullmatch(w["text"]):
                    continue
                matches = [c for c in cols if abs(c["x1"] - w["x1"]) <= tolerance]
                if len(matches) == 1:
                    cells.setdefault(matches[0]["id"], []).append(w)
            # Incomplete/duplicate rows are rejected, including a missing comparison column.
            if len(cells) != len(cols) or any(len(v) != 1 for v in cells.values()):
                if cells:
                    skipped.append({"header_index": header_index, "row_word_ids": [w["id"] for w in local],
                                    "reason": "incomplete_or_duplicate_column_alignment"})
                continue
            edge = min(v[0]["x0"] for v in cells.values())
            label = [w for w in local if w["x1"] < edge - 2]
            while label and (label[0]["text"].isdigit() or re.fullmatch(r"[IVX]+", label[0]["text"])):
                label = label[1:]
            if not label or not any(ch.isalpha() for w in label for ch in w["text"]):
                continue
            # Do not silently truncate a wrapped label into a seemingly complete fact.
            next_rows = [r for r in rows if 0 < min(w["top"] for w in r) - max(w["top"] for w in row) <
                         max(w["bottom"] - w["top"] for w in row) * 1.7]
            continuation = any(any(h["left"] < w["x0"] < edge and any(c.isalpha() for c in w["text"]) for w in r)
                               and not any(abs(w["x1"] - c["x1"]) <= tolerance and NUMBER.fullmatch(w["text"])
                                           for w in r for c in cols) for r in next_rows)
            if continuation:
                skipped.append({"header_index": header_index, "row_word_ids": [w["id"] for w in local],
                                "reason": "possible_wrapped_label_or_adjacent_heading"})
                continue
            for c in cols:
                value = cells[c["id"]][0]
                reasons = []
                if unit is None:
                    reasons.append("missing_or_ambiguous_unit")
                if scope is None:
                    reasons.append("missing_or_ambiguous_statement_scope")
                if value["text"] == "-":
                    reasons.append("dash_is_not_zero")
                if any("/" in w["text"] for w in label):
                    reasons.append("row_specific_unit_or_ratio_requires_review")
                fields = {"label": locator(label), "value": locator([value]), "period": locator([c]),
                          "unit": unit, "statement_scope": scope}
                identity = {"extractor": EXTRACTOR, "content_hash": content_hash, "page": page_number,
                            "header_index": header_index, "fields": fields}
                candidates.append({"cell_id": sha256(canonical(identity)), **identity,
                                   "year": YEAR.fullmatch(c["text"])[1], "review_reasons": reasons,
                                   "structural_status": "needs_review" if reasons else "linked_candidate",
                                   "semantic_support": "not_assessed", "human_reviewed": False})
    return {"extractor": EXTRACTOR, "pdfplumber_version": pdfplumber.__version__,
            "content_hash": content_hash, "page": page_number, "width": width, "height": height,
            "coordinate_system": "PDF points; top-left origin; word boxes, not character offsets",
            "words": words, "header_diagnostics": diagnostics, "skipped_rows": skipped, "cells": candidates}


def extract_page(payload, content_hash, page_number):
    if sha256(payload) != content_hash:
        raise ValueError("Raw PDF checksum mismatch")
    if len(payload) > 128 * 1024 * 1024 or type(page_number) is not int or page_number < 1:
        raise ValueError("PDF byte/page budget exceeded")
    with pdfplumber.open(io.BytesIO(payload)) as pdf:
        if page_number > len(pdf.pages):
            raise ValueError("PDF page does not exist")
        page = pdf.pages[page_number - 1]
        if page.rotation:
            raise ValueError("Rotated PDF pages require a separately validated extractor")
        raw = page.dedupe_chars().extract_words(x_tolerance=2, y_tolerance=2)
        if len(raw) > 12000:
            raise ValueError("PDF page word budget exceeded")
        usable = [w for w in raw if w.get("upright", True) and
                  0 <= w["x0"] < w["x1"] <= page.width and 0 <= w["top"] < w["bottom"] <= page.height]
        words = [{"id": i, "text": w["text"], **{k: round(float(w[k]), 4)
                  for k in ("x0", "x1", "top", "bottom")}} for i, w in enumerate(usable)]
        bundle = bind_words(words, width=float(page.width), height=float(page.height),
                            content_hash=content_hash, page_number=page_number)
        bundle["excluded_outside_or_rotated_words"] = len(raw) - len(usable)
        return bundle


def replay_page(bundle, payload):
    """Re-extract from raw bytes; a self-consistent forged bundle must not pass."""
    if extract_page(payload, bundle["content_hash"], bundle["page"]) != bundle:
        raise ValueError("Table bundle differs from raw PDF extraction")
    return True
