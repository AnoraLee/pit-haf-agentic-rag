"""Verified views and replayable snapshots of unreviewed OCR cell context."""

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from pit_haf.data import ocr_cells, ocr_cells_v02
from pit_haf.data.hub import file_sha
from pit_haf.llm.ollama import write_json
from pit_haf.research.ocr_preview import detail as ocr_detail
from pit_haf.research.ocr_preview import folder_for

MODULES = {"ocr_cell_links_v0.1": ocr_cells, "ocr_cell_links_v0.2": ocr_cells_v02}


def detail(root, run_id, policy_id="ocr_cell_links_v0.1", header_run_id=None):
    if policy_id not in MODULES or (header_run_id and policy_id != "ocr_cell_links_v0.2") or header_run_id == run_id:
        raise ValueError("Header supplements require the spatial OCR policy and a different saved run")
    view = ocr_detail(root, run_id)  # Raw PDF, TSV, registry and saved temporal gate checked first.
    module = MODULES[policy_id]
    policy = module.load_policy(root)
    header_view = ocr_detail(root, header_run_id) if header_run_id else None
    if header_view and (header_view["source"]["version_id"] != view["source"]["version_id"] or
                        header_view["source"]["content_hash"] != view["source"]["content_hash"] or
                        len(header_view["pages"]) != 1 or header_view["pages"][0]["page"] not in {p["page"] for p in view["pages"]}):
        raise ValueError("Header OCR must reference the exact same PDF version and page")
    pages = []
    for page in view["pages"]:
        if policy_id == "ocr_cell_links_v0.1":
            pages.append(module.link_page(page, policy, view["source"]))
            continue
        origins = {w["id"]: {"ocr_run_id": run_id, "word_id": w["id"]} for w in page.get("words", [])}
        diagnostic = None
        if header_view and header_view["pages"][0]["page"] == page["page"]:
            page, origins, diagnostic = module.supplement_page(page, header_view["pages"][0], body_run_id=run_id,
                                                              header_run_id=header_run_id, policy=policy)
        linked = module.link_page(page, policy, view["source"], origins=origins)
        if diagnostic:
            linked["diagnostics"].append(diagnostic)
        pages.append(linked)
    result = {"ocr_run_id": run_id, "ocr_run_seal_sha256": file_sha(folder_for(root, run_id) / "integrity.json"),
            "policy_id": policy["policy_id"], "policy_sha256": file_sha(root / module.POLICY_PATH),
            "source": view["source"], "pages": pages,
            "human_reviewed_facts": 0, "used_in_report_context": False, "historical_availability_validated": False,
            "semantic_accuracy": None, "new_ocr_calls": 0, "new_llm_calls": 0,
            "verification": "saved_OCR_bytes_raw_PDF_images_and_source_gate_checked; cell_links_unreviewed"}
    if policy_id == "ocr_cell_links_v0.2":
        result.update(header_ocr_run_id=header_run_id,
                      header_ocr_seal_sha256=file_sha(folder_for(root, header_run_id) / "integrity.json") if header_run_id else None)
    return result


def save(root, run_id, policy_id="ocr_cell_links_v0.1", header_run_id=None):
    view = detail(root, run_id, policy_id, header_run_id)
    folder = root / "outputs/ocr-cell-links" / (datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid4().hex[:8])
    folder.mkdir(parents=True)
    write_json(folder / "links.json", view)
    (folder / "policy.json").write_bytes((root / MODULES[policy_id].POLICY_PATH).read_bytes())
    (folder / "ocr_cells.py").write_bytes(Path(ocr_cells.__file__).read_bytes())
    (folder / "ocr_cell_links.py").write_bytes(Path(__file__).read_bytes())
    if policy_id == "ocr_cell_links_v0.2":
        (folder / "ocr_cells_v02.py").write_bytes(Path(ocr_cells_v02.__file__).read_bytes())
    write_json(folder / "integrity.json", {"files": {p.name: file_sha(p) for p in folder.iterdir() if p.is_file()}})
    return folder, view


def replay(root, folder):
    root, folder = root.resolve(), folder.resolve()
    if folder.parent != root / "outputs/ocr-cell-links":
        raise ValueError("OCR cell-link replay must stay in project outputs")
    seal = json.loads((folder / "integrity.json").read_text(encoding="utf-8"))
    if not {"links.json", "policy.json", "ocr_cells.py", "ocr_cell_links.py"} <= set(seal["files"]):
        raise ValueError("Incomplete OCR cell-link snapshot")
    for name, digest in seal["files"].items():
        path = folder / name
        if path.is_symlink() or not path.resolve().is_relative_to(folder) or file_sha(path) != digest:
            raise ValueError("OCR cell-link snapshot checksum mismatch")
    saved = json.loads((folder / "links.json").read_text(encoding="utf-8"))
    if file_sha(folder / "policy.json") != saved["policy_sha256"]:
        raise ValueError("OCR cell-link saved policy hash differs")
    if saved["policy_id"] == "ocr_cell_links_v0.2" and "ocr_cells_v02.py" not in seal["files"]:
        raise ValueError("Spatial OCR snapshot is missing its implementation")
    if detail(root, saved["ocr_run_id"], saved["policy_id"], saved.get("header_ocr_run_id")) != saved:
        raise ValueError("Replayed OCR cell links differ from saved context")
    return saved


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--ocr-run")
    group.add_argument("--replay", type=Path)
    parser.add_argument("--policy", choices=list(MODULES))
    parser.add_argument("--header-run")
    args = parser.parse_args()
    if args.replay:
        if args.policy or args.header_run:
            parser.error("Replay uses its saved policy/header run; omit overrides")
        folder, view = args.replay, replay(args.root, args.replay)
    else:
        folder, view = save(args.root.resolve(), args.ocr_run, args.policy or "ocr_cell_links_v0.1", args.header_run)
    print(json.dumps({"path": str(folder), "ocr_run_id": view["ocr_run_id"],
                      "cells": sum(len(p["cells"]) for p in view["pages"]), "new_ocr_calls": 0, "new_llm_calls": 0}))


if __name__ == "__main__":
    main()
