"""Literal OCR-cell diagnostics against assistant transcriptions; never independent gold."""

import argparse
import json
import math
import re
import uuid
from datetime import UTC, datetime
from pathlib import Path

from pit_haf.data.hub import file_sha
from pit_haf.llm.ollama import write_json
from pit_haf.research.ocr_preview import detail, read_sealed


def validate_references(data):
    if (data.get("provenance") != "assistant_visual_transcription" or data.get("independent_gold") is not False or
            data.get("human_confirmed") is not False or data.get("allowed_use") != "development_diagnostic_only" or
            not re.fullmatch(r"[a-f0-9]{64}", data.get("content_hash", "")) or
            not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}", data.get("version_id", "")) or
            type(data.get("page")) is not int or not 1 <= data["page"] <= 10000 or
            not 1 <= len(data.get("cells", [])) <= 50):
        raise ValueError("OCR numeric references require explicit assistant/non-gold provenance")
    seen = set()
    for cell in data["cells"]:
        box = cell["bbox_normalized"]
        if (cell["id"] in seen or not re.fullmatch(r"[A-Za-z0-9_-]{1,40}", cell["id"]) or
                len(box) != 4 or any(type(v) not in (int, float) or not math.isfinite(v) for v in box) or
                not (0 <= box[0] < box[2] <= 1 and 0 <= box[1] < box[3] <= 1) or
                not re.fullmatch(r"(?:\d[\d.,]*|\(\d[\d.,]*\)|-)", cell["literal"]) or
                not cell.get("column_label") or
                cell.get("resolved_year") is not None):
            raise ValueError("Invalid/duplicate OCR reference cell or unverified year assignment")
        seen.add(cell["id"])
    return data


def compare(view, references):
    refs = validate_references(references)
    if (view["source"]["content_hash"] != refs["content_hash"] or
            view["source"]["version_id"] != refs["version_id"]):
        raise ValueError("OCR diagnostic source differs from reference PDF version/hash")
    page = next((p for p in view["pages"] if p["page"] == refs["page"] and p["status"] == "ocr_unreviewed"), None)
    if page is None:
        raise ValueError("OCR diagnostic reference page is missing or failed")
    iw, ih = page["geometry"]["image_width"], page["geometry"]["image_height"]
    rows = []
    for cell in refs["cells"]:
        box = cell["bbox_normalized"]
        words = [w for w in page["words"] if box[0] <= (w["bbox_pixels"][0] + w["bbox_pixels"][2]) / (2 * iw) <= box[2]
                 and box[1] <= (w["bbox_pixels"][1] + w["bbox_pixels"][3]) / (2 * ih) <= box[3]]
        words.sort(key=lambda w: (w["bbox_pixels"][0], w["bbox_pixels"][1], w["id"]))
        observed = " ".join(w["text"] for w in words)
        compact = re.sub(r"\s+", "", observed)
        expected = cell["literal"]
        issues = []
        if not words:
            issues.append("missing_value")
        if len(words) > 1:
            issues.append("fragmented_tokens")
        if observed.count("(") != observed.count(")"):
            issues.append("unbalanced_parentheses")
        if re.search(r"[^\d\s.,()\-]", observed):
            issues.append("non_numeric_characters")
        if len({tuple(w["reading_order"][k] for k in ("block_num", "par_num", "line_num")) for w in words}) > 1:
            issues.append("multiple_text_lines")
        if compact != expected:
            issues.append("punctuation_or_sign_mismatch" if re.sub(r"\D", "", compact) == re.sub(r"\D", "", expected)
                          else "value_mismatch")
        if expected == "-":
            issues.append("dash_is_not_zero")
        rows.append({"id": cell["id"], "bbox_normalized": box, "column_label": cell["column_label"],
                     "resolved_year": None, "expected_assistant_literal": expected, "observed": observed,
                     "word_ids": [w["id"] for w in words], "literal_match": observed == expected,
                     "whitespace_only_match": compact == expected, "issues": issues,
                     "semantic_support": "not_assessed", "human_reviewed": False})
    return {"run_id": view["run"]["run_id"], "profile_id": view["run"]["profile_id"], "page": refs["page"],
            "reference_provenance": refs["provenance"], "independent_gold": False, "semantic_accuracy": None,
            "cells_checked": len(rows), "literal_matches": sum(x["literal_match"] for x in rows),
            "whitespace_only_matches": sum(x["whitespace_only_match"] for x in rows), "cells": rows,
            "limitations": "Assistant same-source development transcription; no financial accuracy or absolute year inferred."}


def audit(root, reference_path, run_ids):
    reference_path = reference_path.resolve()
    if not reference_path.is_relative_to(root.resolve()) or not 1 <= len(run_ids) <= 8 or len(set(run_ids)) != len(run_ids):
        raise ValueError("OCR diagnostic needs a local reference file and 1–8 distinct runs")
    refs = validate_references(json.loads(reference_path.read_text(encoding="utf-8")))
    rows, seals = [], {}
    for run_id in run_ids:
        folder, _, _ = read_sealed(root, run_id)
        seals[run_id] = file_sha(folder / "integrity.json")
        rows.append(compare(detail(root, run_id), refs))
    destination = root / "outputs/ocr-numeric-audits" / (datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8])
    destination.mkdir(parents=True)
    (destination / "references.json").write_bytes(reference_path.read_bytes())
    (destination / "ocr_numeric.py").write_bytes(Path(__file__).read_bytes())
    write_json(destination / "audit.json", {"references_sha256": file_sha(reference_path), "run_seals": seals,
               "results": rows, "development_only": True, "new_ocr_calls": 0, "new_llm_calls": 0})
    write_json(destination / "integrity.json", {"files": {p.name: file_sha(p) for p in destination.iterdir() if p.is_file()}})
    return destination, rows


def replay(root, folder):
    root, folder = root.resolve(), folder.resolve()
    if folder.parent != root / "outputs/ocr-numeric-audits":
        raise ValueError("OCR diagnostic audit folder must stay in project outputs")
    seal = json.loads((folder / "integrity.json").read_text(encoding="utf-8"))
    if not {"audit.json", "references.json", "ocr_numeric.py"} <= set(seal["files"]):
        raise ValueError("Incomplete OCR diagnostic audit")
    for name, digest in seal["files"].items():
        path = folder / name
        if path.is_symlink() or not path.resolve().is_relative_to(folder) or file_sha(path) != digest:
            raise ValueError("OCR diagnostic audit checksum mismatch")
    saved = json.loads((folder / "audit.json").read_text(encoding="utf-8"))
    refs = validate_references(json.loads((folder / "references.json").read_text(encoding="utf-8")))
    if (saved["references_sha256"] != file_sha(folder / "references.json") or
            not saved["development_only"] or saved["new_ocr_calls"] != 0 or saved["new_llm_calls"] != 0):
        raise ValueError("OCR diagnostic audit provenance mismatch")
    rows = []
    for run_id, digest in saved["run_seals"].items():
        run_folder, _, _ = read_sealed(root, run_id)
        if file_sha(run_folder / "integrity.json") != digest:
            raise ValueError("OCR diagnostic source run seal differs")
        rows.append(compare(detail(root, run_id), refs))
    if rows != saved["results"]:
        raise ValueError("Replayed OCR diagnostic differs from saved comparisons")
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--references", type=Path)
    parser.add_argument("--runs", nargs="+")
    parser.add_argument("--replay", type=Path)
    args = parser.parse_args()
    if args.replay:
        folder, rows = args.replay, replay(args.root, args.replay)
    else:
        if not args.references or not args.runs:
            parser.error("--references and --runs are required without --replay")
        folder, rows = audit(args.root.resolve(), args.references, args.runs)
    print(json.dumps({"path": str(folder), "summaries": [{k: x[k] for k in (
        "run_id", "cells_checked", "literal_matches", "whitespace_only_matches")} for x in rows]}))


if __name__ == "__main__":
    main()
