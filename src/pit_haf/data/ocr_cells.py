"""Generic same-line OCR cell links for review, with no repaired text or financial facts."""

import json
import re
from collections import defaultdict
from statistics import median

from pit_haf.data.financial_sections import normalized
from pit_haf.data.snapshots import canonical
from pit_haf.llm.ollama import sha256

POLICY_PATH = "configs/ocr_cell_links_v0_1.json"
POLICY = {"policy_id": "ocr_cell_links_v0.1", "status": "development_not_frozen",
          "right_edge_tolerance_fraction": .008, "min_anchor_rows": 3, "min_anchor_digits": 4,
          "min_columns": 2, "max_columns": 8, "max_cells": 120, "header_distance_fraction": .18,
          "max_phrase_word_gap_in_heights": 2, "low_confidence_threshold": 80,
          "require_complete_period_row": True, "require_period_label_prefix": True,
          "join_wrapped_labels": False, "infer_relative_years": False, "automatic_facts": False}
NUMBER = re.compile(r"(?:[+−-]?[0-9]+(?:[.,][0-9]+)*|\([0-9]+(?:[.,][0-9]+)*\)|-)$")
YEAR = re.compile(r"(?:19|20)[0-9]{2}$")
UNITS = {"vnd": "VND", "dong": "VND", "trieu dong": "million_VND", "trieu vnd": "million_VND",
         "ty dong": "billion_VND", "ty vnd": "billion_VND", "nghin dong": "thousand_VND"}
SCOPES = {"hop nhat": "consolidated", "rieng le": "parent", "cong ty me": "parent"}
RELATIVE = {"nam nay": "relative_current", "nam truoc": "relative_previous"}
PREFIXES = {"chi tieu": "column_labels", "noi dung": "column_labels", "khoan muc": "column_labels", "stt": "column_labels"}


def load_policy(root):
    policy = json.loads((root / POLICY_PATH).read_text(encoding="utf-8"))
    if policy != POLICY:
        raise ValueError("Unknown OCR cell-link policy or budget")
    return policy


def line_key(word):
    return tuple(word["reading_order"][k] for k in ("block_num", "par_num", "line_num"))


def locator(words):
    return {"text": " ".join(w["text"] for w in words), "word_ids": [w["id"] for w in words],
            "bbox_pixels": [min(w["bbox_pixels"][0] for w in words), min(w["bbox_pixels"][1] for w in words),
                            max(w["bbox_pixels"][2] for w in words), max(w["bbox_pixels"][3] for w in words)],
            "word_boxes": [w["bbox_pixels"] for w in words],
            "minimum_confidence": min(w["confidence"] for w in words), "human_reviewed": False,
            "origin": "ocr_unreviewed"}


def phrases(rows, aliases, policy):
    result = []
    for row in rows:
        found = []
        for size in range(1, 4):
            for i in range(len(row) - size + 1):
                part = row[i:i + size]
                key = normalized(" ".join(w["text"] for w in part))
                if key not in aliases:
                    continue
                if any(b["bbox_pixels"][0] - a["bbox_pixels"][2] > policy["max_phrase_word_gap_in_heights"] *
                       max(a["bbox_pixels"][3] - a["bbox_pixels"][1], b["bbox_pixels"][3] - b["bbox_pixels"][1])
                       for a, b in zip(part, part[1:])):
                    continue
                found.append({"observed_value": aliases[key], **locator(part)})
        # The token 'đồng' inside 'triệu đồng' is not a second conflicting unit.
        result.extend(a for a in found if not any(set(a["word_ids"]) < set(b["word_ids"]) for b in found))
    return result


def columns(words, width, policy):
    tolerance = width * policy["right_edge_tolerance_fraction"]
    seeds = [w for w in words if NUMBER.fullmatch(w["text"]) and not YEAR.fullmatch(w["text"]) and
             len(re.sub(r"[^0-9]", "", w["text"])) >= policy["min_anchor_digits"]]
    clusters = []
    for word in sorted(seeds, key=lambda w: (w["bbox_pixels"][2], w["id"])):
        if clusters and abs(word["bbox_pixels"][2] - median(w["bbox_pixels"][2] for w in clusters[-1])) <= tolerance:
            clusters[-1].append(word)
        else:
            clusters.append([word])
    usable = [group for group in clusters if len({line_key(w) for w in group}) >= policy["min_anchor_rows"]]
    if not policy["min_columns"] <= len(usable) <= policy["max_columns"]:
        return []
    result = [{"column_id": f"X{i + 1}", "right_edge": median(w["bbox_pixels"][2] for w in group),
               "left_edge": min(w["bbox_pixels"][0] for w in group),
               "center": median((w["bbox_pixels"][0] + w["bbox_pixels"][2]) / 2 for w in group),
               "anchor_rows": len({line_key(w) for w in group}), "seed_word_ids": [w["id"] for w in group]}
              for i, group in enumerate(usable)]
    if any(b["right_edge"] - a["right_edge"] <= tolerance * 2 for a, b in zip(result, result[1:])):
        return []
    return result


def link_page(page, policy, source):
    """Input is a verified OCR page. Relative years and all financial facts stay unresolved."""
    output = {"page": page["page"], "status": page["status"], "cells": [], "columns": [], "diagnostics": [],
              "human_reviewed_facts": 0, "used_in_report_context": False, "semantic_accuracy": None}
    if page["status"] != "ocr_unreviewed":
        output["diagnostics"].append({"reason": "ocr_page_failed"})
        return output
    words, geometry = page["words"], page["geometry"]
    width, height = geometry["image_width"], geometry["image_height"]
    cols = columns(words, width, policy)
    output["columns"] = cols
    if not cols:
        output["diagnostics"].append({"reason": "missing_or_ambiguous_numeric_columns"})
        return output
    rows = defaultdict(list)
    for word in words:
        rows[line_key(word)].append(word)
    rows = [sorted(row, key=lambda w: (w["bbox_pixels"][0], w["id"])) for row in rows.values()]
    rows.sort(key=lambda row: (min(w["bbox_pixels"][1] for w in row), line_key(row[0])))
    tolerance = width * policy["right_edge_tolerance_fraction"]
    assignments = {}
    for word in words:
        if not NUMBER.fullmatch(word["text"]) or YEAR.fullmatch(word["text"]):
            continue
        matches = [c for c in cols if abs(c["right_edge"] - word["bbox_pixels"][2]) <= tolerance]
        if len(matches) == 1:
            assignments[word["id"]] = matches[0]["column_id"]
    values = [w for w in words if w["id"] in assignments]
    first_top = min(w["bbox_pixels"][1] for w in values)
    label_edge = min(w["bbox_pixels"][0] for w in values)
    header_rows = [[w for w in row if first_top - height * policy["header_distance_fraction"] <= w["bbox_pixels"][1]
                    and w["bbox_pixels"][3] < first_top] for row in rows]
    header_rows = [row for row in header_rows if row]
    unit_refs, scope_refs = phrases(header_rows, UNITS, policy), phrases(header_rows, SCOPES, policy)
    periods, accepted_period_rows, rejected_period_rows = [], [], []
    radius = min(b["center"] - a["center"] for a, b in zip(cols, cols[1:])) * .45
    for row in header_rows:
        local = phrases([row], RELATIVE, policy)
        local.extend({"observed_value": "absolute_year", "observed_year": int(w["text"]), **locator([w])}
                     for w in row if YEAR.fullmatch(w["text"]))
        periods.extend(local)
        if not local:
            continue
        grouped = defaultdict(list)
        for period in local:
            center = (period["bbox_pixels"][0] + period["bbox_pixels"][2]) / 2
            matches = [c for c in cols if abs(c["center"] - center) <= radius]
            if len(matches) == 1:
                grouped[matches[0]["column_id"]].append(period)
        prefix = phrases([row], PREFIXES, policy)
        kinds = [(p["observed_value"], p.get("observed_year")) for p in local]
        if (len(grouped) != len(cols) or any(len(g) != 1 for g in grouped.values()) or
                len(local) != len(cols) or len(kinds) != len(set(kinds)) or
                not any(p["bbox_pixels"][2] < min(g["bbox_pixels"][0] for g in local) for p in prefix)):
            rejected_period_rows.append({"reason": "incomplete_ambiguous_or_unprefixed_period_row",
                                         "word_ids": [w["id"] for w in row]})
        else:
            accepted_period_rows.append(grouped)
    period_by_column = accepted_period_rows[0] if len(accepted_period_rows) == 1 else {}
    header_info = {"reason": "observed_header_context", "units": unit_refs, "statement_scopes": scope_refs,
                   "periods": periods, "rejected_period_rows": rejected_period_rows,
                   "accepted_period_rows": len(accepted_period_rows), "relative_years_not_inferred": True}
    output["diagnostics"].append(header_info)
    for row in rows:
        row_values = [w for w in row if w["id"] in assignments]
        if not row_values:
            continue
        by_column = defaultdict(list)
        for word in row_values:
            by_column[assignments[word["id"]]].append(word)
        if any(len(group) != 1 for group in by_column.values()):
            output["diagnostics"].append({"reason": "duplicate_values_in_column_line", "word_ids": [w["id"] for w in row]})
            continue
        for col in cols:
            group = by_column.get(col["column_id"], [])
            nearby = [w for w in row if col["left_edge"] - tolerance <=
                      (w["bbox_pixels"][0] + w["bbox_pixels"][2]) / 2 <= col["right_edge"] + tolerance]
            if group and (len(nearby) != 1 or nearby[0]["id"] != group[0]["id"]):
                output["diagnostics"].append({"reason": "fragmented_or_extra_column_tokens", "column_id": col["column_id"],
                                             "word_ids": [w["id"] for w in nearby]})
                del by_column[col["column_id"]]
        row_values = [w for w in row_values if assignments[w["id"]] in by_column]
        labels = [w for w in row if w["bbox_pixels"][2] < label_edge and w["id"] not in assignments]
        labels = labels if any(any(c.isalpha() for c in w["text"]) for w in labels) else []
        for value in row_values:
            col_id = assignments[value["id"]]
            refs = period_by_column.get(col_id, [])
            period = refs[0] if len(refs) == 1 else None
            fields = {"label": locator(labels) if labels else None, "value": locator([value]),
                      "period": period, "unit": unit_refs[0] if len(unit_refs) == 1 else None,
                      "statement_scope": scope_refs[0] if len(scope_refs) == 1 else None}
            reasons = ["ocr_text_unreviewed", "label_semantics_unverified", "same_line_label_may_be_incomplete"]
            reasons.extend("missing_or_ambiguous_" + name for name, ref in fields.items() if ref is None)
            if not period or period["observed_value"] != "absolute_year":
                reasons.append("absolute_year_unresolved")
            if len(by_column) != len(cols):
                reasons.append("incomplete_numeric_row")
            if any(ref and ref["minimum_confidence"] < policy["low_confidence_threshold"] for ref in fields.values()):
                reasons.append("low_confidence_field")
            if labels and not any(min(w["bbox_pixels"][3], value["bbox_pixels"][3]) >
                                  max(w["bbox_pixels"][1], value["bbox_pixels"][1]) for w in labels):
                reasons.append("label_value_alignment_uncertain")
            if value["text"] == "-":
                reasons.append("dash_is_not_zero")
            identity = {"policy_id": policy["policy_id"], "version_id": source["version_id"],
                        "content_hash": source["content_hash"], "page": page["page"], "column_id": col_id, "fields": fields}
            output["cells"].append({"candidate_id": sha256(canonical(identity)), **identity,
                                    "observed_year": period.get("observed_year") if period else None,
                                    "resolved_year": None, "structural_status": "needs_review", "review_reasons": reasons,
                                    "human_reviewed": False, "semantic_support": "not_assessed", "automatic_fact": False})
    if len(output["cells"]) > policy["max_cells"]:
        output["diagnostics"].append({"reason": "cell_budget_exceeded", "count": len(output["cells"])})
        output["cells"] = []
    return output
