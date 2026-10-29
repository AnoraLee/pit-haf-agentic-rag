"""Unfrozen retrieval-only development comparison; never changes the active case pack."""

import argparse
import json
import re
import uuid
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

from pit_haf.data.catalog import Catalog
from pit_haf.data.financial_sections import PROFILE, search_financial
from pit_haf.data.hub import file_sha
from pit_haf.data.retrieval_scope import ReportScope
from pit_haf.llm.ollama import write_json
from pit_haf.research.doctor import capture_repository
from pit_haf.research.evaluation import pinned_context
from pit_haf.research.reports import PROTOCOL, RETRIEVAL_POLICY, run_report, select_context
from pit_haf.research.reviews import active_pack
from pit_haf.research.source_audit import load_source_audit
from pit_haf.verification.quotes import normalized_space


def coverage(sources, terms):
    """Diagnostic string presence, not evidence sufficiency or semantic correctness."""
    spans = [normalized_space(s["passage"]["text"]) for s in sources]
    return sum(any(normalized_space(t) in p for p in spans) for t in terms)


def build_study(root):
    index, cases = active_pack(root)
    pack = root / "outputs/development-cases" / index["pack_id"]
    summary = json.loads((pack / "summary.json").read_text(encoding="utf-8"))
    catalog = Catalog(root, root / summary["snapshot"])
    audit = load_source_audit(root)
    audit_rows = {r["case_id"]: r for r in audit["rows"]} if audit else {}
    study_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]
    folder = root / "outputs/retrieval-development" / study_id
    folder.mkdir(parents=True, exist_ok=False)
    repository = capture_repository(root, folder)
    profile_hash = file_sha(root / PROFILE)
    rows, diagnostics = [], []
    for case in cases.values():
        pinned_context(summary, case, catalog)
        scope = ReportScope.model_validate(case["retrieval_scope"])
        data, hits, trace = search_financial(catalog, case["query"], scope=scope)
        if trace["profile_sha256"] != profile_hash:
            raise ValueError("Retrieval profile changed during the development study")
        selected = select_context(data, hits, case["ticker"], mode="exploratory_current", scope=scope)
        rows.append({**case, "evidence": selected, "retrieval_trace": trace})
        terms = sorted({span["anchor"] for cite in audit_rows.get(case["case_id"], {}).get("citations", [])
                        for span in cite["spans"]})
        diagnostic = {"case_id": case["case_id"], "ticker": case["ticker"],
                      "old_pages": [s["passage"]["page"] for s in case["evidence"]],
                      "new_pages": [s["passage"]["page"] for s in selected],
                      "references": len(selected), "context_characters": sum(len(s["passage"]["text"]) for s in selected),
                      "assistant_audit_anchors": len(terms), "old_anchor_hits": coverage(case["evidence"], terms),
                      "new_anchor_hits": coverage(selected, terms)}
        diagnostics.append(diagnostic)
        print(json.dumps(diagnostic, ensure_ascii=False), flush=True)
    (folder / "cases.jsonl").write_bytes(("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n").encode())
    totals = Counter()
    for row in diagnostics:
        for key in ("references", "assistant_audit_anchors", "old_anchor_hits", "new_anchor_hits"):
            totals[key] += row[key]
    result = {"study_id": study_id, "run_kind": "retrieval_development_not_final_experiment",
              "created_at": datetime.now(UTC).isoformat(), "repository": repository,
              "baseline_pack_id": index["pack_id"], "baseline_cases_sha256": index["cases_sha256"],
              "profile_file": PROFILE, "profile_sha256": profile_hash,
              "protocol_sha256": file_sha(root / PROTOCOL), "retrieval_policy_sha256": file_sha(root / RETRIEVAL_POLICY),
              "snapshot": summary["snapshot"], "summary_sha256": summary["summary_sha256"],
              "catalog_sha256": summary["catalog_sha256"], "cases_sha256": file_sha(folder / "cases.jsonl"),
              "cases": len(rows), "diagnostics": diagnostics, "totals": dict(totals),
              "assistant_audit_is_not_independent_gold": True, "semantic_accuracy": None,
              "historical_availability_validated": False, "llm_inference_performed": False,
              "active_pack_changed": False,
              "limitations": ["Development heuristics informed by prior errors; not held-out retrieval evaluation.",
                              "Anchor hits mean string presence only, not correct row/column/period or semantic support.",
                              "Same legacy 3 passages/2100 chars, prompt, schema and numeric verifier; header/quote limitations remain."]}
    write_json(folder / "summary.json", result)
    write_json(folder / "integrity.json", {"summary_sha256": file_sha(folder / "summary.json")})
    return folder, result


def run_smoke(root, folder):
    """Exactly one income question per published ticker, preselected before outcomes."""
    base = (root / "outputs/retrieval-development").resolve()
    if folder.resolve().parent != base or folder.is_symlink() or not re.fullmatch(r"\d{8}T\d{6}Z-[0-9a-f]{8}", folder.name):
        raise ValueError("Smoke study must be a sealed folder inside outputs/retrieval-development")
    summary = json.loads((folder / "summary.json").read_text(encoding="utf-8"))
    seal = json.loads((folder / "integrity.json").read_text(encoding="utf-8"))
    if (file_sha(folder / "summary.json") != seal["summary_sha256"] or
            file_sha(folder / "cases.jsonl") != summary["cases_sha256"] or
            file_sha(root / PROFILE) != summary["profile_sha256"] or
            file_sha(root / PROTOCOL) != summary["protocol_sha256"] or
            file_sha(root / RETRIEVAL_POLICY) != summary["retrieval_policy_sha256"]):
        raise ValueError("Retrieval study/profile checksum mismatch")
    cases = [json.loads(line) for line in (folder / "cases.jsonl").read_text(encoding="utf-8").splitlines()]
    index, original = active_pack(root)
    if (summary["baseline_pack_id"] != index["pack_id"] or summary["baseline_cases_sha256"] != index["cases_sha256"] or
            [c["case_id"] for c in cases] != list(original)):
        raise ValueError("Smoke source pack differs from the active baseline")
    snapshot = (root / summary["snapshot"]).resolve()
    if not snapshot.is_relative_to((root / "outputs/milestone-1/data-pilot").resolve()):
        raise ValueError("Smoke catalog must stay inside the published data-pilot directory")
    selected = [c for c in cases if c["case_id"].endswith("-income")]
    if len(selected) != 3:
        raise ValueError("This smoke run requires exactly three preselected income cases")
    catalog = Catalog(root, snapshot)
    results = []
    # No retries/replacement of failed cases, and no active-pack publication.
    with (folder / "smoke.json").open("x", encoding="utf-8") as stream:
        manifest = {"selection": "First income case for each ticker, before inference outcomes",
                    "study_id": summary["study_id"], "runs": results, "model_digest": None}
        for case in selected:
            data, hits, scope = pinned_context(summary, case, catalog)
            report = run_report(root, data, hits, query=case["question"], ticker=case["ticker"],
                                mode="exploratory_current", scope=scope, expected_sources=case["evidence"],
                                expected_model_digest=manifest["model_digest"], retrieval_trace=case["retrieval_trace"])
            if manifest["model_digest"] is None:
                manifest["model_digest"] = report.get("model_before", {}).get("digest")
            results.append({"case_id": case["case_id"], "run_id": report["run_id"], "status": report["status"],
                            "accepted_claims": len(report["claims"]), "rejected_claims": len(report["rejected_claims"]),
                            "report_sha256": file_sha(Path(report["path"]) / "report.json")})
            stream.seek(0)
            json.dump(manifest, stream, ensure_ascii=False, indent=2)
            stream.truncate()
            stream.flush()
            print(json.dumps(results[-1], ensure_ascii=False), flush=True)
            attempts = (report.get("generation") or {}).get("attempts", [])
            if (report["status"] == "failed" or report.get("model_digest_stable") is False or
                    any(a.get("failure") in {"timeout", "transport_error", "oom"} for a in attempts)):
                break
    write_json(folder / "smoke-integrity.json", {"smoke_sha256": file_sha(folder / "smoke.json")})
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--smoke-study", type=Path, help="Existing study folder; three bounded real local calls")
    args = parser.parse_args()
    if args.smoke_study:
        print(json.dumps(run_smoke(args.root.resolve(), args.smoke_study.resolve()), ensure_ascii=False))
    else:
        folder, summary = build_study(args.root.resolve())
        print(json.dumps({"path": str(folder), "totals": summary["totals"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
