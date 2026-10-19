"""Prepare reproducible development cases; no automatic promotion to human gold."""

import argparse
import json
import uuid
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

from pit_haf.data.catalog import Catalog
from pit_haf.data.evidence import aware
from pit_haf.data.hub import file_sha
from pit_haf.llm.ollama import sha256, write_json
from pit_haf.research.doctor import capture_repository
from pit_haf.research.reports import PROTOCOL, ReportDraft, protocol, select_context, verify_claims


def build_pack(root, output_base=None):
    settings = protocol(root)
    paths = sorted(root.glob("outputs/milestone-1/data-pilot/*/summary.json"),
                   key=lambda p: p.stat().st_mtime_ns, reverse=True)
    if not paths:
        raise ValueError("A published disk catalog is required")
    catalog = Catalog(root, paths[0])
    pack_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]
    destination = (output_base or root / "outputs/development-cases") / pack_id
    destination.mkdir(parents=True, exist_ok=False)
    repository = capture_repository(root, destination)
    cases, index, annotations = [], [], []
    for ticker in settings["pilot_tickers"]:
        for task in settings["case_queries"]:
            data, hits = catalog.search(task["query"], ticker=ticker)
            selected = select_context(data, hits, ticker, mode="exploratory_current")
            case_id = f"dev01-{ticker}-{task['id']}"
            cases.append({"case_id": case_id, "data_kind": "real_document_development_candidate",
                          "ticker": ticker, "question": task["question"], "query": task["query"],
                          "mode": "exploratory_current", "evidence": selected})
            index.append({"case_id": case_id, "ticker": ticker, "question": task["question"],
                          "query": task["query"], "review_status": "pending", "references": [{
                              "evidence_id": s["evidence_id"], "version_id": s["source"]["version_id"],
                              "content_hash": s["source"]["content_hash"], "source_url": s["source"]["source_url"],
                              "origin": s["source"]["origin"], "page": s["passage"]["page"],
                              "start": s["passage"]["start"], "end": s["passage"]["end"],
                              "page_text_hash": s["passage"]["page_text_hash"],
                              "context_sha256": sha256(s["passage"]["text"].encode()),
                          } for s in selected]})
            annotations.append({"case_id": case_id, "status": "pending", "reviewer": None,
                                "reviewed_at": None, "answers": [], "notes": ""})
            print(json.dumps({"prepared": len(cases), "case_id": case_id, "passages": len(selected)}), flush=True)
    for name, rows in (("cases.jsonl", cases), ("annotations.template.jsonl", annotations)):
        (destination / name).write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows),
                                        encoding="utf-8", newline="\n")
    review = ["# Phiếu duyệt case phát triển", "", "Chưa có đáp án chuẩn hoặc người duyệt.",
              "Đọc câu hỏi và nguồn; đánh dấu sai kỳ/không trả lời được thay vì suy diễn đáp án.", ""]
    for case in cases:
        review.extend([f"## {case['case_id']}", "", case["question"], "",
                       "Trạng thái: pending. Người duyệt: _____. Đáp án và lý do: _____", ""])
        for source in case["evidence"]:
            p, v = source["passage"], source["source"]
            review.extend([f"### {source['evidence_id']} — {v['title']}", "",
                           f"Nguồn: {v['source_url']}",
                           f"Trang/mục {p['page']}; ký tự {p['start']}–{p['end']}; phiên bản {v['version_id']}.",
                           "", "> " + p["text"].replace("\n", "\n> "), ""])
    (destination / "review.md").write_text("\n".join(review), encoding="utf-8", newline="\n")
    report = {"pack_id": pack_id, "created_at": datetime.now(UTC).isoformat(),
              "run_kind": "development_annotation_candidates_not_human_gold", "protocol_frozen": False,
              "repository": repository,
              "protocol_id": settings["protocol_id"], "protocol_sha256": file_sha(root / PROTOCOL),
              "snapshot": catalog.snapshot, "summary_sha256": catalog.pointer["summary_sha256"],
              "catalog_sha256": catalog.pointer["catalog_sha256"],
              "selection": "Eight prespecified topic queries per ticker; current-corpus FTS5 top six; diversify and bound to three passages/2100 characters. No selection by return or model success.",
              "cases": len(cases), "cases_with_evidence": sum(bool(c["evidence"]) for c in cases),
              "by_ticker": dict(Counter(c["ticker"] for c in cases)), "human_reviewed_cases": 0,
              "historical_availability_validated": False, "llm_inference_performed": False,
              "cases_sha256": file_sha(destination / "cases.jsonl"),
              "annotations_template_sha256": file_sha(destination / "annotations.template.jsonl"),
              "index": index}
    write_json(destination / "summary.json", report)
    return destination, report


def check_reviews(pack, annotations_path):
    summary = json.loads((pack / "summary.json").read_text(encoding="utf-8"))
    if file_sha(pack / "cases.jsonl") != summary["cases_sha256"]:
        raise ValueError("Development source cases checksum mismatch")
    cases = {r["case_id"]: r for r in map(json.loads, (pack / "cases.jsonl").read_text(encoding="utf-8").splitlines())}
    seen, counts = set(), Counter()
    for annotation in map(json.loads, annotations_path.read_text(encoding="utf-8").splitlines()):
        case_id = annotation["case_id"]
        if case_id in seen or case_id not in cases:
            raise ValueError("Unknown or repeated annotation case")
        seen.add(case_id)
        status = annotation["status"]
        if status == "pending":
            counts["pending"] += 1
            continue
        if status not in {"answered", "unanswerable", "needs_ocr", "wrong_period"}:
            raise ValueError("Unknown annotation status")
        if not isinstance(annotation.get("reviewer"), str) or not annotation["reviewer"].strip():
            raise ValueError("A named human reviewer is required")
        aware(datetime.fromisoformat(str(annotation.get("reviewed_at")).replace("Z", "+00:00")), "reviewed_at")
        if status == "answered":
            draft = ReportDraft(claims=annotation["answers"], missing_information=[], insufficient_evidence=False)
            accepted, rejected = verify_claims(draft, cases[case_id]["evidence"], True)
            if not accepted or rejected:
                raise ValueError("Reviewed answer has an invalid literal locator or numeric string: " + case_id)
        elif annotation.get("answers") or not str(annotation.get("notes") or "").strip():
            raise ValueError("Non-answer cases require a reason and no supported answers")
        counts[status] += 1
    if seen != set(cases):
        raise ValueError("Every development case must retain a review row")
    reviewed = len(cases) - counts["pending"]
    return {"run_kind": "human_annotation_integrity_check_not_independent_semantic_validation",
            "cases": len(cases), "human_reviewed_cases_declared": reviewed,
            "counts": dict(counts), "ready_for_reviewed_development_scoring": reviewed == len(cases),
            "historical_availability_validated": False, "annotations_sha256": file_sha(annotations_path)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--check-reviews", type=Path)
    args = parser.parse_args()
    if args.check_reviews:
        if not args.pack:
            parser.error("--check-reviews requires --pack")
        print(json.dumps(check_reviews(args.pack, args.check_reviews), ensure_ascii=False))
    else:
        destination, report = build_pack(args.root.resolve())
        print(json.dumps({"path": str(destination), "cases": report["cases"],
                          "human_reviewed_cases": 0}, ensure_ascii=False))


if __name__ == "__main__":
    main()
