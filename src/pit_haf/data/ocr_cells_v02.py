"""Spatial OCR links and explicit same-page header supplements; all remain unreviewed."""

import json
import re
from copy import deepcopy
from datetime import date
from statistics import median

from pit_haf.data import ocr_cells as base
from pit_haf.data.financial_sections import normalized
from pit_haf.data.snapshots import canonical
from pit_haf.llm.ollama import sha256

POLICY_PATH = "configs/ocr_cell_links_v0_2.json"
POLICY = {**base.POLICY, "policy_id": "ocr_cell_links_v0.2", "header_distance_fraction": .30,
          "join_wrapped_labels": True, "spatial_row_tolerance_in_heights": .45,
          "max_label_lines": 3, "label_distance_in_heights": 2.2, "max_label_indent_in_heights": 3,
          "max_label_line_gap_in_heights": 1.8, "max_header_region_height_fraction": .10,
          "infer_relative_years": False, "automatic_facts": False}


def load_policy(root):
    policy = json.loads((root / POLICY_PATH).read_text(encoding="utf-8"))
    if policy != POLICY:
        raise ValueError("Unknown spatial OCR cell-link policy or budget")
    return policy


def spatial_rows(words, policy):
    if not words:
        return []
    font = median(w["bbox_pixels"][3] - w["bbox_pixels"][1] for w in words)
    rows = []
    for word in sorted(words, key=lambda w: ((w["bbox_pixels"][1] + w["bbox_pixels"][3]) / 2, w["bbox_pixels"][0], w["id"])):
        center = (word["bbox_pixels"][1] + word["bbox_pixels"][3]) / 2
        if rows and abs(center - median((w["bbox_pixels"][1] + w["bbox_pixels"][3]) / 2 for w in rows[-1])) <= font * policy["spatial_row_tolerance_in_heights"]:
            rows[-1].append(word)
        else:
            rows.append([word])
    return [sorted(row, key=lambda w: (w["bbox_pixels"][0], w["id"])) for row in rows]


def statement_period(rows, first_top, height, policy):
    found = []
    pattern = r"(?:cho )?nam tai chinh ket thuc ngay ([0-9]{1,2}) thang ([0-9]{1,2}) nam ((?:19|20)[0-9]{2})"
    for row in rows:
        if not all(first_top - height * policy["header_distance_fraction"] <= w["bbox_pixels"][1] and
                   w["bbox_pixels"][3] < first_top for w in row):
            continue
        match = re.fullmatch(pattern, normalized(" ".join(w["text"] for w in row)))
        if match:
            day, month, year = map(int, match.groups())
            try:
                end = date(year, month, day)
            except ValueError:
                continue
            found.append({**base.locator(row), "observed_value": "annual_statement_period",
                          "observed_end_date": end.isoformat(), "observed_statement_year": year})
    return found[0] if len(found) == 1 else None


def label_parts(rows, center, low, high, edge, font, policy):
    parts = []
    for row in rows:
        left = [w for w in row if w["bbox_pixels"][2] < edge]
        if not left:
            continue
        y = median((w["bbox_pixels"][1] + w["bbox_pixels"][3]) / 2 for w in left)
        if not (low < y < high and abs(y - center) <= font * policy["label_distance_in_heights"]):
            continue
        text = " ".join(w["text"] for w in left).strip()
        letters = [c for c in text if c.isalpha()]
        if (not letters or text.endswith(":") or re.match(r"^[IVX]+\.", text) or
                (len(left) >= 2 and sum(c.isupper() for c in letters) / len(letters) > .85)):
            continue
        parts.append(left)
    if not 1 <= len(parts) <= policy["max_label_lines"]:
        return []
    for previous, following in zip(parts, parts[1:]):
        first = following[0]["text"].lstrip()
        acronym = len(first) <= 8 and first.isupper()
        if (not first or (not first[0].islower() and first[0] not in "([" and not acronym) or
                abs(following[0]["bbox_pixels"][0] - parts[0][0]["bbox_pixels"][0]) > font * policy["max_label_indent_in_heights"] or
                min(w["bbox_pixels"][1] for w in following) - max(w["bbox_pixels"][3] for w in previous) >
                font * policy["max_label_line_gap_in_heights"]):
            return []
    return parts


def link_page(page, policy, source, *, origins=None):
    if page["status"] != "ocr_unreviewed":
        return base.link_page(page, policy, source)
    rows = spatial_rows(page["words"], policy)
    working = []
    for i, row in enumerate(rows, 1):
        working.extend({**w, "reading_order": {"block_num": 1, "par_num": 1, "line_num": i, "word_num": j}}
                       for j, w in enumerate(row, 1))
    result = base.link_page({**page, "words": working}, policy, source)
    result["diagnostics"].append({"reason": "spatial_rows_rebuilt", "word_ids_by_row": [[w["id"] for w in row] for row in rows]})
    if not result["cells"]:
        return result
    lookup = {w["id"]: w for w in working}
    value_words = [lookup[c["fields"]["value"]["word_ids"][0]] for c in result["cells"]]
    first_top = min(w["bbox_pixels"][1] for w in value_words)
    edge = min(w["bbox_pixels"][0] for w in value_words)
    font = median(w["bbox_pixels"][3] - w["bbox_pixels"][1] for w in page["words"])
    period = statement_period(rows, first_top, page["geometry"]["image_height"], policy)
    context = next(d for d in result["diagnostics"] if d["reason"] == "observed_header_context")
    units = [ref for ref in context["units"] if normalized(ref["text"]) != "dong" or
             ref["text"].casefold().strip(" .,:;") in {"đồng", "dong"}]
    if len(units) != len(context["units"]):
        result["diagnostics"].append({"reason": "non_currency_homograph_rejected",
                                      "rejected_unit_word_ids": [r["word_ids"] for r in context["units"] if r not in units]})
    centers = {}
    for word in value_words:
        centers.setdefault(base.line_key(word), []).append((word["bbox_pixels"][1] + word["bbox_pixels"][3]) / 2)
    ordered = sorted((median(ys), key) for key, ys in centers.items())
    labels_by_line = {}
    for i, (center, key) in enumerate(ordered):
        low = (ordered[i - 1][0] + center) / 2 if i else center - font * policy["label_distance_in_heights"]
        high = (ordered[i + 1][0] + center) / 2 if i + 1 < len(ordered) else center + font * policy["label_distance_in_heights"]
        labels_by_line[key] = label_parts(rows, center, low, high, edge, font, policy)
    for cell in result["cells"]:
        key = base.line_key(lookup[cell["fields"]["value"]["word_ids"][0]])
        parts = labels_by_line[key]
        fields = cell["fields"]
        fields["label"] = base.locator([w for part in parts for w in part]) if parts else None
        fields["statement_period"] = deepcopy(period)
        fields["unit"] = deepcopy(units[0]) if len(units) == 1 else None
        cell["label_parts"] = [base.locator(p) for p in parts]
        cell["observed_statement_year"] = period["observed_statement_year"] if period else None
        reasons = [r for r in cell["review_reasons"] if r not in {
            "same_line_label_may_be_incomplete", "low_confidence_field", "missing_or_ambiguous_label", "label_value_alignment_uncertain"}]
        if fields["unit"] is not None:
            reasons = [r for r in reasons if r != "missing_or_ambiguous_unit"]
        elif "missing_or_ambiguous_unit" not in reasons:
            reasons.append("missing_or_ambiguous_unit")
        reasons.append("spatial_label_requires_review")
        if not parts:
            reasons.append("missing_or_ambiguous_label")
        if len(parts) > 1:
            reasons.append("wrapped_label_requires_review")
        if period is None:
            reasons.append("missing_or_ambiguous_statement_period")
        if any(ref and ref["minimum_confidence"] < policy["low_confidence_threshold"] for ref in fields.values()):
            reasons.append("low_confidence_field")
        cell["review_reasons"] = reasons
        for ref in [*fields.values(), *cell["label_parts"]]:
            if ref and origins is not None:
                ref["word_refs"] = [origins[w] for w in ref["word_ids"]]
        identity = {k: cell[k] for k in ("policy_id", "version_id", "content_hash", "page", "column_id", "fields")}
        cell["candidate_id"] = sha256(canonical(identity))
    return result


def supplement_page(body, header, *, body_run_id, header_run_id, policy):
    """Replace only an explicit header strip. Numeric body and source images cannot change."""
    if (body["status"] != "ocr_unreviewed" or header["status"] != "ocr_unreviewed" or
            body["page"] != header["page"] or body["image_sha256"] != header["image_sha256"] or
            any(body["geometry"][k] != header["geometry"][k] for k in ("image_width", "image_height", "dpi", "rotation"))):
        raise ValueError("Header supplement must match the same successful PDF page/image geometry")
    region = header["geometry"].get("ocr_region_normalized")
    columns = base.columns(body["words"], body["geometry"]["image_width"], policy)
    seeds = [w for w in body["words"] if any(w["id"] in c["seed_word_ids"] for c in columns)]
    if not region or not seeds or region[3] - region[1] > policy["max_header_region_height_fraction"]:
        raise ValueError("Header supplement needs a small explicit region and body numeric columns")
    box = header["geometry"]["ocr_crop_pixels"]
    if box[3] >= min(w["bbox_pixels"][1] for w in seeds):
        raise ValueError("Header supplement must stay above all body numeric rows")
    if box[0] > min(c["left_edge"] for c in columns) or box[2] < max(c["right_edge"] for c in columns):
        raise ValueError("Header supplement must cover every numeric column")
    origins = {w["id"]: {"ocr_run_id": body_run_id, "word_id": w["id"]} for w in body["words"]}
    removed, kept = [], []
    for word in body["words"]:
        b = word["bbox_pixels"]
        (removed if box[0] <= (b[0] + b[2]) / 2 <= box[2] and box[1] <= (b[1] + b[3]) / 2 <= box[3] else kept).append(word)
    for word in header["words"]:
        new_id = "H:" + word["id"]
        kept.append({**word, "id": new_id})
        origins[new_id] = {"ocr_run_id": header_run_id, "word_id": word["id"]}
    return {**body, "words": kept}, origins, {"reason": "explicit_same_page_header_supplement",
             "header_ocr_run_id": header_run_id, "region": region,
             "superseded_body_words": [{"id": w["id"], "text": w["text"]} for w in removed]}
