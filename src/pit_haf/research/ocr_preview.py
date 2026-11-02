"""Audited OCR preview only: no automatic facts, corpus replacement or LLM context."""

import argparse
import json
import re
import sqlite3
import uuid
from datetime import UTC, datetime
from pathlib import Path

from pit_haf.data import pdf_ocr, pdf_ocr_worker
from pit_haf.data.catalog import Catalog
from pit_haf.data.evidence import EvidenceVersion
from pit_haf.data.hub import file_sha
from pit_haf.data.pdf_ocr import (
    PROFILES,
    crop_input,
    model_directory,
    parse_tsv,
    render_page,
    run_worker,
    settings,
    validate_pages,
    validate_region,
)
from pit_haf.data.retrieval_scope import DocumentReportScope, check_document_scope
from pit_haf.data.snapshots import SnapshotStore
from pit_haf.llm.ollama import sha256, write_json
from pit_haf.research.reports import retrieval_access
from pit_haf.research.table_documents import annual_scope

RUN_PATTERN = r"\d{8}T\d{6}Z-[0-9a-f]{8}"


def catalog_for(root):
    summaries = sorted(root.glob("outputs/milestone-1/data-pilot/*/summary.json"),
                       key=lambda p: p.stat().st_mtime_ns, reverse=True)
    if not summaries or not (summaries[0].parent / "catalog.json").is_file():
        raise ValueError("OCR preview requires the published document catalog")
    return Catalog(root, summaries[0])


def folder_for(root, run_id):
    if not re.fullmatch(RUN_PATTERN, run_id):
        raise ValueError("Invalid OCR run ID")
    base = root / "outputs/ocr-previews"
    folder = base / run_id
    if (not base.resolve().is_relative_to(root.resolve()) or folder.is_symlink() or
            folder.resolve().parent != base.resolve()):
        raise ValueError("OCR run must stay in the project output folder")
    return folder


def run(root, *, query, ticker, version_id, pages, reporting_period=None,
        mode="exploratory_current", decision_at=None, worker=None, profile_id="pdf_ocr_preview_v0.1", region=None):
    root = root.resolve()
    profile = settings(root, profile_id)
    wanted = validate_pages(pages, profile["max_pages"])
    selected_region = validate_region(region, profile)
    scope = annual_scope(query, ticker, reporting_period=reporting_period, version_id=version_id)
    allowed, audit = retrieval_access(root, mode, decision_at)
    if allowed is not None and version_id not in allowed:
        raise ValueError("Selected OCR document was not delivered by the Point-in-Time gateway")
    catalog = catalog_for(root)
    check_document_scope(catalog, scope, allowed)
    source, _, _ = catalog.page(version_id, 1)
    store = catalog.store
    raw = store.read_blob(source.content_hash)
    if len(raw) > profile["max_pdf_bytes"]:
        raise ValueError("OCR PDF byte budget exceeded")
    run_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]
    folder = folder_for(root, run_id)
    folder.mkdir(parents=True, exist_ok=False)
    code = folder / "implementation"
    code.mkdir()
    for name, path in (("ocr_preview.py", Path(__file__)), ("pdf_ocr.py", Path(pdf_ocr.__file__)),
                       ("pdf_ocr_worker.py", Path(pdf_ocr_worker.__file__))):
        (code / name).write_bytes(path.read_bytes())
    (folder / "ocr-profile.json").write_bytes((root / PROFILES[profile_id]).read_bytes())
    if (root / "uv.lock").is_file():
        (code / "uv.lock").write_bytes((root / "uv.lock").read_bytes())
    write_json(folder / "source.json", source.model_dump(mode="json"))
    write_json(folder / "gateway-audit.json", audit)
    result = {"run_id": run_id, "run_kind": "ocr_preview_development_not_financial_facts",
              "profile_id": profile["profile_id"], "profile_sha256": file_sha(root / PROFILES[profile_id]),
              "question": query, "ticker": ticker, "version_id": version_id,
              "scope": scope.model_dump(), "mode": mode, "decision_at": decision_at,
              "requested_pages": wanted, "pages": [], "model_hashes": profile["models"],
              "llm_calls": 0, "human_reviewed_facts": 0, "semantic_accuracy": None,
              "historical_availability_validated": False, "used_in_report_context": False,
              "status": "started"}
    if selected_region is not None:
        result["requested_region"] = selected_region
    execute = worker or run_worker
    for number in wanted:
        destination = folder / f"page-{number:04d}"
        destination.mkdir()
        row = {"page": number, "folder": destination.name}
        try:
            kwargs = {"region": selected_region} if selected_region is not None else {}
            data = execute(root, store.blob_path(source.content_hash), source.content_hash, number, destination, profile, **kwargs)
            row.update(status="ocr_unreviewed", word_count=data["word_count"],
                       low_confidence_words=data["low_confidence_words"])
        except (OSError, ValueError, RuntimeError, KeyError, TypeError) as exc:
            row.update(status="failed", error_type=type(exc).__name__, error=str(exc))
        result["pages"].append(row)
        write_json(folder / "result.json", result)
    failures = sum(p["status"] == "failed" for p in result["pages"])
    result["status"] = "failed" if failures == len(wanted) else "partial_failure" if failures else "ocr_unreviewed"
    write_json(folder / "result.json", result)
    write_json(folder / "integrity.json", {"files": {p.relative_to(folder).as_posix(): file_sha(p)
               for p in sorted(folder.rglob("*")) if p.is_file()}})
    return folder, result


def read_sealed(root, run_id):
    folder = folder_for(root, run_id)
    manifest = json.loads((folder / "integrity.json").read_text(encoding="utf-8"))
    if not {"result.json", "source.json", "gateway-audit.json", "ocr-profile.json"} <= set(manifest["files"]):
        raise ValueError("OCR run is incomplete")
    for name, digest in manifest["files"].items():
        path = folder / name
        if path.is_symlink() or not path.resolve().is_relative_to(folder.resolve()) or file_sha(path) != digest:
            raise ValueError("OCR artifact checksum/locator mismatch")
    result = json.loads((folder / "result.json").read_text(encoding="utf-8"))
    profile = settings(root, result["profile_id"])
    profile_path = root / PROFILES[result["profile_id"]]
    if file_sha(folder / "ocr-profile.json") != file_sha(profile_path):
        raise ValueError("Saved OCR profile differs from current versioned settings")
    if (result["run_id"] != run_id or result["run_kind"] != "ocr_preview_development_not_financial_facts" or
            result["profile_id"] != profile["profile_id"] or result["profile_sha256"] != file_sha(profile_path) or
            result["llm_calls"] != 0 or result["human_reviewed_facts"] != 0 or result["semantic_accuracy"] is not None or
            result["used_in_report_context"] or result["historical_availability_validated"] or
            result["model_hashes"] != profile["models"]):
        raise ValueError("OCR profile/status identity mismatch")
    requested = validate_pages(result["requested_pages"], profile["max_pages"])
    region = validate_region(result.get("requested_region"), profile)
    if requested != result["requested_pages"] or [p["page"] for p in result["pages"]] != requested:
        raise ValueError("OCR page selection differs from saved request")
    source = EvidenceVersion.model_validate_json((folder / "source.json").read_bytes())
    scope = DocumentReportScope.model_validate(result["scope"])
    if (not scope.matches(source) or source.version_id != result["version_id"] or
            source.ticker != result["ticker"] or scope.source_policy != "issuer_reports"):
        raise ValueError("OCR source violates document/company/period scope")
    store = SnapshotStore(root / "data/cache/evidence")
    with sqlite3.connect(store.database.resolve().as_uri() + "?mode=ro", uri=True) as db:
        row = db.execute("SELECT metadata_json,metadata_hash FROM versions WHERE version_id=?", (source.version_id,)).fetchone()
    if (row is None or sha256(row[0].encode()) != row[1] or
            EvidenceVersion.model_validate_json(row[0]) != source):
        raise ValueError("OCR source differs from immutable registry")
    allowed, _ = retrieval_access(root, result["mode"], result["decision_at"])
    if allowed is not None and source.version_id not in allowed:
        raise ValueError("OCR source no longer passes its saved temporal gate")
    for page in result["pages"]:
        if page["folder"] != f"page-{page['page']:04d}" or page["status"] not in {"ocr_unreviewed", "failed"}:
            raise ValueError("Invalid OCR page folder/status")
        if page["status"] == "failed":
            continue
        directory = folder / page["folder"]
        names = {f"{page['folder']}/{n}" for n in ("page.png", "page.tsv", "page.txt", "page.json")}
        if not names <= set(manifest["files"]):
            raise ValueError("OCR page is incomplete")
        data = json.loads((directory / "page.json").read_text(encoding="utf-8"))
        if (data["geometry"]["page"] != page["page"] or not data["ocr_performed"] or
                data["human_reviewed_facts"] != 0 or data["semantic_support"] != "not_assessed" or
                data["tesserocr_version"] != profile["tesserocr_version"] or
                data["engine"].splitlines()[0] != profile["tesseract_version"]):
            raise ValueError("OCR page/engine identity mismatch")
        if data["geometry"].get("ocr_region_normalized") != region:
            raise ValueError("OCR geometry differs from saved region selection")
        if region is not None:
            name = f"{page['folder']}/ocr-input.png"
            if name not in manifest["files"] or data.get("ocr_input_sha256") != file_sha(folder / name):
                raise ValueError("OCR crop input checksum mismatch")
        if any(data[key] != file_sha(directory / name) for key, name in (
            ("image_sha256", "page.png"), ("text_sha256", "page.txt"), ("tsv_sha256", "page.tsv")
        )):
            raise ValueError("OCR page checksum mismatch")
        words = parse_tsv((directory / "page.tsv").read_text(encoding="utf-8"), data["geometry"], profile)
        if (data["words"] != words or not page["word_count"] == data["word_count"] == len(words) or
                not page["low_confidence_words"] == data["low_confidence_words"] == sum(w["low_confidence"] for w in words)):
            raise ValueError("OCR words differ from raw TSV")
    failures = sum(p["status"] == "failed" for p in result["pages"])
    expected_status = "failed" if failures == len(requested) else "partial_failure" if failures else "ocr_unreviewed"
    if result["status"] != expected_status:
        raise ValueError("OCR run status differs from saved page outcomes")
    return folder, result, source


def detail(root, run_id):
    folder, result, source = read_sealed(root, run_id)
    profile = settings(root, result["profile_id"])
    raw = SnapshotStore(root / "data/cache/evidence").read_blob(source.content_hash)
    pages = []
    for page in result["pages"]:
        if page["status"] == "failed":
            pages.append(page)
            continue
        directory = folder / page["folder"]
        data = json.loads((directory / "page.json").read_text(encoding="utf-8"))
        png, geometry = render_page(raw, source.content_hash, page["page"], profile, region=result.get("requested_region"))
        if geometry != data["geometry"] or sha256(png) != data["image_sha256"]:
            raise ValueError("OCR image differs from raw PDF rendering")
        if result.get("requested_region") is not None and sha256(crop_input(png, geometry)) != data["ocr_input_sha256"]:
            raise ValueError("OCR input crop differs from raw PDF image")
        pages.append({**page, **data, "text": (directory / "page.txt").read_text(encoding="utf-8"),
                      "image_url": f"/api/research/ocr-previews/{run_id}/pages/{page['page']}/image"})
    return {"run": result, "source": {k: source.model_dump(mode="json")[k] for k in (
                "version_id", "title", "ticker", "reporting_period", "source_url", "content_hash")},
            "pages": pages, "verification": "saved_bytes_and_raw_pdf_images; OCR_not_rerun",
            "confidence_basis": "Tesseract heuristic score, not a probability of correctness"}


def history(root, version_id=None):
    rows = []
    for folder in sorted((root / "outputs/ocr-previews").glob("*"), reverse=True)[:30]:
        if not re.fullmatch(RUN_PATTERN, folder.name):
            continue
        try:
            _, result, _ = read_sealed(root, folder.name)
            if version_id and result["version_id"] != version_id:
                continue
            rows.append({**{k: result[k] for k in ("run_id", "ticker", "version_id", "status", "requested_pages", "profile_id")},
                         "requested_region": result.get("requested_region")})
        except (OSError, ValueError, KeyError, TypeError):
            rows.append({"run_id": folder.name, "status": "integrity_failed"})
    return rows


def page_image(root, run_id, number):
    folder, result, source = read_sealed(root, run_id)
    page = next((p for p in result["pages"] if p["page"] == number and p["status"] == "ocr_unreviewed"), None)
    if page is None:
        raise KeyError("OCR page image does not exist")
    data = json.loads((folder / page["folder"] / "page.json").read_text(encoding="utf-8"))
    store = SnapshotStore(root / "data/cache/evidence")
    png, geometry = render_page(store.read_blob(source.content_hash), source.content_hash, number,
                                settings(root, result["profile_id"]), region=result.get("requested_region"))
    if sha256(png) != data["image_sha256"] or geometry != data["geometry"]:
        raise ValueError("OCR page image differs from raw PDF")
    return png


def replay(root, folder, worker=None):
    # Re-run OCR in a new folder, preserving every original run byte.
    view = detail(root, folder.name)
    checked, result, source = read_sealed(root, folder.name)
    if checked.resolve() != folder.resolve():
        raise ValueError("OCR replay directory identity mismatch")
    if not any(p["status"] == "ocr_unreviewed" for p in result["pages"]):
        raise ValueError("No successful OCR page to rerun; saved failures are preserved")
    profile = settings(root, result["profile_id"])
    store = SnapshotStore(root / "data/cache/evidence")
    output = root / "outputs/ocr-replays" / (folder.name + "-" + uuid.uuid4().hex[:8])
    output.mkdir(parents=True)
    execute = worker or run_worker
    for page in view["pages"]:
        if page["status"] == "failed":
            continue
        destination = output / f"page-{page['page']:04d}"
        destination.mkdir()
        kwargs = {"region": result["requested_region"]} if result.get("requested_region") is not None else {}
        fresh = execute(root, store.blob_path(source.content_hash), source.content_hash, page["page"], destination, profile, **kwargs)
        expected = json.loads((folder / page["folder"] / "page.json").read_text(encoding="utf-8"))
        if fresh != expected:
            raise ValueError("Replayed OCR differs from saved raw text/TSV/geometry/runtime")
    write_json(output / "replay.json", {"run_id": result["run_id"], "ocr_replay": "passed",
               "successful_pages_rerun": sum(p["status"] == "ocr_unreviewed" for p in result["pages"]),
               "failed_pages_preserved": sum(p["status"] == "failed" for p in result["pages"])})
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--setup-models", action="store_true")
    parser.add_argument("--ticker")
    parser.add_argument("--query")
    parser.add_argument("--document-version")
    parser.add_argument("--pages", type=int, nargs="+")
    parser.add_argument("--reporting-period")
    parser.add_argument("--profile", choices=list(PROFILES), default="pdf_ocr_preview_v0.1")
    parser.add_argument("--region", type=float, nargs=4, help="x0 y0 x1 y1 as full-page fractions, region profile only")
    parser.add_argument("--mode", choices=["exploratory_current", "strict_point_in_time"], default="exploratory_current")
    parser.add_argument("--decision-at")
    parser.add_argument("--replay", type=Path)
    args = parser.parse_args()
    root = args.root.resolve()
    if args.setup_models:
        settings(root)
        print(json.dumps({"models": str(model_directory(root, download=True)), "network_during_ocr": False}))
    elif args.replay:
        result = replay(root, args.replay.resolve())
        print(json.dumps({"run_id": result["run_id"], "ocr_replay": "passed", "llm_calls": 0}))
    else:
        if not all((args.query, args.ticker, args.document_version, args.pages)):
            parser.error("--ticker, --query, --document-version and --pages are required")
        folder, result = run(root, query=args.query, ticker=args.ticker, version_id=args.document_version,
                             pages=args.pages, reporting_period=args.reporting_period, mode=args.mode, decision_at=args.decision_at,
                             profile_id=args.profile, region=args.region)
        print(json.dumps({"path": str(folder), "status": result["status"], "pages": result["pages"], "llm_calls": 0}))


if __name__ == "__main__":
    main()
