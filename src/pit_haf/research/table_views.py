"""Read-only, checksummed table-run views and source-page rendering for the local UI."""

import io
import json
import re
from urllib.parse import quote

import pdfplumber

from pit_haf.data.hub import file_sha
from pit_haf.data.snapshots import SnapshotStore
from pit_haf.research.table_evidence import replay


def run_folder(root, run_id):
    if not re.fullmatch(r"\d{8}T\d{6}Z-[0-9a-f]{8}", run_id):
        raise ValueError("Invalid table run ID")
    base = root / "outputs/table-evidence"
    folder = base / run_id
    if (not base.resolve().is_relative_to(root.resolve()) or folder.is_symlink() or
            folder.resolve().parent != base.resolve()):
        raise ValueError("Table run locator must stay in the project")
    return folder


def read_sealed(root, run_id):
    folder = run_folder(root, run_id)
    manifest = json.loads((folder / "integrity.json").read_text(encoding="utf-8"))
    required = {"result.json", "context.json", "gateway-audit.json", "retrieval-trace.json"}
    if not required <= set(manifest["files"]):
        raise ValueError("Table run is incomplete/unsealed")
    for name, digest in manifest["files"].items():
        path = folder / name
        if path.is_symlink() or not path.resolve().is_relative_to(folder.resolve()) or file_sha(path) != digest:
            raise ValueError("Table run file checksum/locator mismatch")
    result = json.loads((folder / "result.json").read_text(encoding="utf-8"))
    if (result["run_id"] != run_id or result["run_kind"] != "table_cell_development_not_final_experiment" or
            any(not re.fullmatch(r"table-0[1-3]\.json", name) or name not in manifest["files"]
                for name in result["source_files"])):
        raise ValueError("Invalid table run/source identity")
    return folder, result


def history(root, ticker=None):
    result = []
    for folder in sorted((root / "outputs/table-evidence").glob("*"), reverse=True)[:30]:
        if not re.fullmatch(r"\d{8}T\d{6}Z-[0-9a-f]{8}", folder.name):
            continue
        try:
            _, saved = read_sealed(root, folder.name)
            if ticker and saved["ticker"] != ticker:
                continue
            result.append({**{k: saved[k] for k in ("run_id", "ticker", "question", "status", "profile_id", "mode")},
                           "context_cells": saved.get("context_cells", 0), "llm_calls": saved["llm_calls"],
                           "selected_candidates": len(saved["selected_candidates"]),
                           "integrity": "saved_bytes_checked; raw_PDF_replay_on_open"})
        except (OSError, ValueError, KeyError, TypeError):
            result.append({"run_id": folder.name, "status": "integrity_failed"})
    return result[:20]


def detail(root, run_id):
    folder, _ = read_sealed(root, run_id)
    result = replay(root, folder)
    context = json.loads((folder / "context.json").read_text(encoding="utf-8"))
    sources, cells = [], []
    bundles = [json.loads((folder / name).read_text(encoding="utf-8")) for name in result["source_files"]]
    locations = {(b["source"]["version_id"], b["table"]["page"], c["cell_id"]): (i, c)
                 for i, b in enumerate(bundles, 1) for c in b["table"]["cells"]}
    selected = {c["candidate_id"] for c in result["selected_candidates"]}
    for i, name in enumerate(result["source_files"], 1):
        b = bundles[i - 1]
        source, table = b["source"], b["table"]
        sources.append({"index": i, "page": table["page"], "version_id": source["version_id"],
                        "title": source["title"], "width": table["width"], "height": table["height"],
                        "content_hash": source["content_hash"], "extractor": table["extractor"],
                        "image_url": f"/api/research/table-evidence/{run_id}/pages/{i}/image",
                        "raw_url": f"/api/documents/{quote(source['version_id'], safe='')}/raw#page={table['page']}"})
        lookup = {c["cell_id"]: c for c in table["cells"]}
        for c in context:
            if c["version_id"] == source["version_id"] and c["page"] == table["page"]:
                original = lookup[c["cell_id"]]
                alternatives = []
                for ref in c.get("equivalent_candidates", [c]):
                    source_index, raw_cell = locations[(ref["version_id"], ref["page"], ref["cell_id"])]
                    alternatives.append({"source_index": source_index, "page": ref["page"],
                                         "cell_id": ref["cell_id"], "header_index": raw_cell["header_index"],
                                         "fields": raw_cell["fields"]})
                cells.append({**c, "source_index": i, "context_ref": f"C{context.index(c) + 1}",
                              "fields": original["fields"],
                              "source_alternatives": alternatives,
                              "model_selected": c["candidate_id"] in selected})
    audit = None
    if result.get("context_policy_id"):
        raw = json.loads((folder / "context-audit.json").read_text(encoding="utf-8"))
        audit = {"policy_id": raw["policy_id"], "filtered_cells": len(raw["excluded"]),
                 "duplicate_groups": len(raw["duplicate_groups"]), "grouped_duplicate_cells": raw["grouped_duplicate_cells"],
                 "conflict_groups": len(raw["conflict_groups"]), "query_supported": raw["query_supported"]}
    return {"run": {k: result[k] for k in ("run_id", "ticker", "question", "status", "mode", "profile_id", "llm_calls")},
            "cells": cells, "sources": sources, "context_audit": audit, "replay": "passed", "human_reviewed_facts": 0,
            "semantic_accuracy": None, "historical_availability_validated": False,
            "missing_information": ((result.get("generation") or {}).get("output") or {}).get("missing_information", [])}


def page_image(root, run_id, index):
    folder, result = read_sealed(root, run_id)
    if not 1 <= index <= len(result["source_files"]):
        raise KeyError("Source page index does not exist")
    b = json.loads((folder / result["source_files"][index - 1]).read_text(encoding="utf-8"))
    payload = SnapshotStore(root / "data/cache/evidence").read_blob(b["source"]["content_hash"])
    table = b["table"]
    with pdfplumber.open(io.BytesIO(payload)) as pdf:
        p = pdf.pages[table["page"] - 1]
        if p.rotation or (float(p.width), float(p.height)) != (table["width"], table["height"]):
            raise ValueError("Source image geometry differs from table page")
        image = p.to_image(width=1500, antialias=True).original
        output = io.BytesIO()
        image.save(output, format="PNG")
        return output.getvalue()
