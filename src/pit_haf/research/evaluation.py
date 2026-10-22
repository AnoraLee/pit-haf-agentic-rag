"""Sequential pinned-case development runs and mechanical annotation comparison."""

import argparse
import json
import math
import re
import time
import uuid
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from statistics import median

from pit_haf.data.catalog import Catalog
from pit_haf.data.hub import file_sha
from pit_haf.data.retrieval_scope import ReportScope
from pit_haf.llm.ollama import sha256, write_json
from pit_haf.llm.pilot import number_supported
from pit_haf.research.doctor import capture_repository
from pit_haf.research.reports import (
    NUMBERS,
    PROTOCOL,
    RETRIEVAL_POLICY,
    ReportDraft,
    messages,
    run_report,
    saved_report,
    select_context,
    verify_claims,
)
from pit_haf.research.reviews import ReviewInput, active_pack, ledger, validate_answer
from pit_haf.ui.workspace import Passage
from pit_haf.verification.quotes import normalized_space

ID = re.compile(r"\d{8}T\d{6}Z-[0-9a-f]{8}")
KIND = "pinned_case_development_batch_not_final_experiment"


def digest(value):
    return sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode())


def folder_for(root, batch_id):
    base = (root / "outputs/development-batches").resolve()
    if not ID.fullmatch(batch_id):
        raise ValueError("Invalid batch ID")
    path = base / batch_id
    if path.resolve().parent != base or path.is_symlink():
        raise ValueError("Batch must stay in its local output directory")
    return path


def pinned_context(summary, case, catalog):
    """Read only pinned pages; never search a changing catalog for a batch case."""
    sources = case["evidence"]
    data = catalog.subset((s["passage"]["version_id"], s["passage"]["page"]) for s in sources)
    hits = [Passage(**s["passage"]) for s in sources]
    scope = ReportScope.model_validate(case["retrieval_scope"]) if case.get("retrieval_scope") else None
    selected = select_context(data, hits, case["ticker"], mode="exploratory_current", scope=scope)
    if selected != sources or data.snapshot != summary["snapshot"]:
        raise ValueError("Pinned source metadata/text/offsets changed")
    return data, hits, scope


def run_batch(root, *, limit=None, adapter=None):
    index, cases = active_pack(root)
    if limit is not None and not 1 <= limit <= len(cases):
        raise ValueError("Limit must be within the case count")
    pack = root / "outputs/development-cases" / index["pack_id"]
    summary = json.loads((pack / "summary.json").read_text(encoding="utf-8"))
    for name, key in ((PROTOCOL, "protocol_sha256"), (RETRIEVAL_POLICY, "retrieval_policy_sha256")):
        if file_sha(root / name) != summary[key]:
            raise ValueError("Case pack protocol/policy changed; publish a new pack first")
    snapshot = (root / summary["snapshot"]).resolve()
    if not snapshot.is_relative_to((root / "outputs/milestone-1/data-pilot").resolve()):
        raise ValueError("Invalid pinned catalog location")
    catalog = Catalog(root, snapshot)
    if any(catalog.pointer[k] != summary[k] for k in ("summary_sha256", "catalog_sha256")):
        raise ValueError("Pinned catalog no longer matches the case pack")
    batch_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]
    destination = folder_for(root, batch_id)
    destination.parent.mkdir(parents=True, exist_ok=True)
    # A killed process leaves this lock for explicit inspection; do not silently resume/retry.
    lock = destination.parent / "run.lock"
    with lock.open("x", encoding="utf-8") as stream:
        stream.write(batch_id)
    result = {"batch_id": batch_id, "created_at": datetime.now(UTC).isoformat(), "run_kind": KIND,
              "pack_id": index["pack_id"], "cases_sha256": index["cases_sha256"],
              "protocol_sha256": summary["protocol_sha256"],
              "retrieval_policy_sha256": summary["retrieval_policy_sha256"],
              "case_pack_summary_sha256": file_sha(pack / "summary.json"),
              "selection": "published case order; optional prefix limit; no success-based replacement",
              "question_basis": "case.question; case.query was used only to build the pinned source pack",
              "requested_cases": limit or len(cases), "status": "running", "model_digest": None,
              "cases": [{"case_id": c, "status": "not_run", "run_id": None} for c in cases],
              "historical_availability_validated": False, "semantic_support": "not_assessed"}
    created = False
    try:
        destination.mkdir(exist_ok=False)
        created = True
        result["repository"] = capture_repository(root, destination)
        write_json(destination / "progress.json", result)
        for row in result["cases"][:result["requested_cases"]]:
            case = cases[row["case_id"]]
            started = time.perf_counter()
            try:
                data, hits, scope = pinned_context(summary, case, catalog)
                report = run_report(root, data, hits, query=case["question"], ticker=case["ticker"],
                                    mode="exploratory_current", scope=scope, adapter=adapter,
                                    expected_sources=case["evidence"],
                                    expected_model_digest=result["model_digest"])
                row.update(status=report["status"], run_id=report["run_id"],
                           report_sha256=file_sha(Path(report["path"]) / "report.json"))
                before = report.get("model_before", {}).get("digest")
                if result["model_digest"] is None and before:
                    result["model_digest"] = before
                attempts = (report.get("generation") or {}).get("attempts", [])
                if (report["status"] == "failed" or report.get("model_digest_stable") is False or
                        any(a.get("failure") in {"timeout", "transport_error", "oom"} for a in attempts)):
                    result["stop_reason"] = "Model failure/digest change; no automatic continuation or retry"
            except (OSError, ValueError, KeyError, TypeError) as exc:
                row.update(status="source_or_runner_failed", error=str(exc))
            row["wall_seconds"] = time.perf_counter() - started
            write_json(destination / "progress.json", result)
            print(json.dumps({"batch_id": batch_id, **row}, ensure_ascii=False), flush=True)
            if result.get("stop_reason"):
                break
        result["status"] = "stopped" if result.get("stop_reason") else "completed"
    except BaseException:
        result["status"] = "interrupted"
        raise
    finally:
        try:
            result["finished_at"] = datetime.now(UTC).isoformat()
            if created:
                write_json(destination / "manifest.json", result)
                write_json(destination / "integrity.json", {"manifest_sha256": file_sha(destination / "manifest.json")})
        finally:
            lock.unlink()
    return result


def load_batch(root, batch_id):
    folder = folder_for(root, batch_id)
    seal = json.loads((folder / "integrity.json").read_text(encoding="utf-8"))
    if file_sha(folder / "manifest.json") != seal["manifest_sha256"]:
        raise ValueError("Batch manifest checksum mismatch")
    batch = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    if batch["batch_id"] != batch_id or batch["run_kind"] != KIND:
        raise ValueError("Batch identity mismatch")
    return batch


def checked_report(root, row, case, batch):
    """Replay byte checks and literal/numeric verifier; no model call during evaluation."""
    report = saved_report(root, row["run_id"])
    folder = root / "outputs/company-reports" / row["run_id"]
    if (file_sha(folder / "report.json") != row["report_sha256"] or report["sources"] != case["evidence"] or
            report["ticker"] != case["ticker"] or report["question"] != case["question"] or
            report["mode"] != "exploratory_current" or report["status"] != row["status"] or
            report["protocol_sha256"] != batch["protocol_sha256"] or
            report["retrieval_policy_sha256"] != batch["retrieval_policy_sha256"]):
        raise ValueError("Report does not match this pinned case/batch")
    generation = report.get("generation")
    if report["llm_calls"] == 0:
        if report["claims"] or report["rejected_claims"] or generation:
            raise ValueError("Unexpected claims without a model call")
        return report
    if report["llm_calls"] != 1 or not generation or generation["attempt_count"] != 1:
        raise ValueError("Expected exactly one audited model attempt")
    attempt = generation["attempts"][0]
    attempt_dir = folder / "generation/attempt-01"
    request = (attempt_dir / "request.json").read_bytes()
    if sha256(request) != generation["request_sha256"] or sha256(request) != attempt["request_sha256"]:
        raise ValueError("Raw model request checksum mismatch")
    payload = json.loads(request)
    config = report["config"]
    if (payload["messages"] != messages(case["question"], case["ticker"], case["evidence"]) or
            payload["model"] != config["model"] or payload["format"] != ReportDraft.model_json_schema() or
            payload["options"] != {k: config[k] for k in ("num_ctx", "num_predict", "temperature", "seed")}):
        raise ValueError("Raw request used different evidence/question")
    if "response_sha256" in attempt:
        response = (attempt_dir / "response.raw").read_bytes()
        if sha256(response) != attempt["response_sha256"]:
            raise ValueError("Raw model response checksum mismatch")
    if generation["output"] is None:
        if report["claims"] or report["rejected_claims"]:
            raise ValueError("Claims from an invalid generation")
        return report
    if "response_sha256" not in attempt:
        raise ValueError("Valid output requires an original response")
    raw_output = json.loads(json.loads(response)["message"]["content"])
    if raw_output != generation["output"]:
        raise ValueError("Parsed output disagrees with original model response")
    before = report["model_before"]["digest"]
    stable = before == report["model_after"]["digest"]
    if before != batch["model_digest"] or stable != report["model_digest_stable"]:
        raise ValueError("Model digest disagrees with the batch")
    accepted, rejected = verify_claims(ReportDraft.model_validate(raw_output), case["evidence"], stable,
                                       entity_review_labels=report["entity_review_labels"])
    if accepted != report["claims"] or rejected != report["rejected_claims"]:
        raise ValueError("Current verifier disagrees with saved claims")
    return report


def span_match(reference, claim):
    a, b = reference["citation"], claim["citation"]
    return (all(a[k] == b[k] for k in ("version_id", "page", "page_text_hash")) and
            max(a["start"], b["start"]) < min(a["end"], b["end"]))


def evaluate_batch(root, batch_id=None):
    index, cases = active_pack(root)
    _, latest = ledger(root, index["pack_id"], index["cases_sha256"])
    for case_id, review in latest.items():
        if case_id not in cases:
            raise ValueError("Review ledger contains an unknown case")
        parsed = ReviewInput.model_validate({k: review[k] for k in ReviewInput.model_fields})
        validate_answer(parsed, cases[case_id])
    if batch_id is None:
        for path in sorted((root / "outputs/development-batches").glob("*/integrity.json"), reverse=True):
            candidate = load_batch(root, path.parent.name)
            if candidate["pack_id"] == index["pack_id"]:
                batch_id = candidate["batch_id"]
                break
    output = {"run_kind": "development_mechanical_evaluation_not_semantic_accuracy",
              "pack_id": index["pack_id"], "cases_sha256": index["cases_sha256"],
              "review_snapshot_sha256": digest({c: r["revision"] for c, r in latest.items()}),
              "total_cases": len(cases), "declared_reviewed_cases": sum(r["status"] != "pending" for r in latest.values()),
              "batch": None, "rows": [], "semantic_accuracy": None,
              "historical_availability_validated": False, "independently_verified_gold_cases": 0}
    if batch_id is None:
        return output
    batch = load_batch(root, batch_id)
    if batch["pack_id"] != index["pack_id"] or batch["cases_sha256"] != index["cases_sha256"]:
        raise ValueError("Batch belongs to a different source pack")
    if [r["case_id"] for r in batch["cases"]] != list(cases):
        raise ValueError("Batch must retain every case exactly once in published order")
    counts, reviewed, blocks, failures = Counter(), Counter(), Counter(), Counter()
    latencies = []
    for item in batch["cases"]:
        case = cases[item["case_id"]]
        review = latest.get(item["case_id"])
        row = {"case_id": item["case_id"], "ticker": case["ticker"], "status": item["status"],
               "run_id": item["run_id"], "review_status": review["status"] if review else "pending"}
        if item.get("error"):
            row["error"] = item["error"]
        counts["total"] += 1
        try:
            if item["run_id"] is None:
                counts[item["status"]] += 1
            else:
                report = checked_report(root, item, case, batch)
                counts["verified_runs"] += 1
                display_status = report["status"]
                if display_status == "abstained" and report["sources"] and not (report.get("generation") or {}).get("output"):
                    display_status = "generation_failed"
                counts[display_status] += 1
                counts["llm_calls"] += report["llm_calls"]
                counts["accepted_claims"] += len(report["claims"])
                counts["rejected_claims"] += len(report["rejected_claims"])
                row.update(status=display_status, accepted_claims=len(report["claims"]), rejected_claims=len(report["rejected_claims"]))
                for claim in report["rejected_claims"]:
                    blocks.update(claim["verification"]["block_reasons"])
                generation = report.get("generation")
                if generation:
                    latencies.append(generation["wall_seconds"])
                    counts["schema_valid_runs"] += generation["output"] is not None
                    for attempt in generation["attempts"]:
                        if attempt.get("failure"):
                            failures[attempt["failure"]] += 1
                        for key in ("prompt_eval_count", "eval_count"):
                            value = (attempt.get("usage") or {}).get(key)
                            if isinstance(value, int):
                                counts[key] += value
                # Invalid JSON/model errors do not count as a successful abstention decision.
                valid = bool(report.get("generation") and report["generation"]["output"] is not None and
                             report.get("model_digest_stable") and report["status"] != "failed")
                if review and review["status"] == "answered" and valid:
                    references, _ = verify_claims(ReportDraft(claims=review["answers"], missing_information=[],
                                                             insufficient_evidence=False), case["evidence"], True)
                    hits = sum(any(span_match(ref, c) for c in report["claims"]) for ref in references)
                    numeric_references, numeric_hits = 0, 0
                    for ref in references:
                        numbers = ref["extracted_numbers"] + [m.group() for m in NUMBERS.finditer(normalized_space(ref["statement"]))]
                        if numbers:
                            numeric_references += 1
                            numeric_hits += any(span_match(ref, c) and all(number_supported(normalized_space(n),
                                normalized_space(c["verification"]["literal_quote"]["source_quote"])) for n in numbers)
                                for c in report["claims"])
                    reviewed["answered_cases_compared"] += 1
                    reviewed["reference_answers"] += len(references)
                    reviewed["reference_spans_hit"] += hits
                    reviewed["numeric_reference_answers"] += numeric_references
                    reviewed["reference_numeric_quotes_hit"] += numeric_hits
                    row.update(reference_answers=len(references), reference_spans_hit=hits,
                               numeric_reference_answers=numeric_references, reference_numeric_quotes_hit=numeric_hits)
                elif review and review["status"] in {"unanswerable", "wrong_period"} and valid:
                    reviewed["nonanswer_cases_compared"] += 1
                    reviewed["nonanswer_cases_without_accepted_claims"] += not bool(report["claims"])
        except (OSError, ValueError, KeyError, TypeError) as exc:
            counts["invalid_runs"] += 1
            row.update(status="integrity_failed", error=str(exc))
        output["rows"].append(row)
    denominator = reviewed["reference_answers"]
    numeric_denominator = reviewed["numeric_reference_answers"]
    output.update(batch={k: batch[k] for k in ("batch_id", "created_at", "status", "requested_cases", "model_digest")},
                  diagnostics=dict(counts), rejected_claim_block_reasons=dict(blocks),
                  generation_failures=dict(failures),
                  inference_seconds={"observations": len(latencies), "total": sum(latencies),
                                     "median": median(latencies) if latencies else None,
                                     "p95_nearest_rank": sorted(latencies)[math.ceil(.95 * len(latencies)) - 1] if latencies else None},
                  annotation_comparison={**dict(reviewed),
                  "reference_span_hit_rate": reviewed["reference_spans_hit"] / denominator if denominator else None,
                  "reference_numeric_quote_hit_rate": reviewed["reference_numeric_quotes_hit"] / numeric_denominator if numeric_denominator else None,
                  "comparison_is_to_reviewer_declarations_not_independent_gold": True,
                  "span_overlap_does_not_verify_answer_meaning": True})
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--limit", type=int, help="Run a published prefix, retaining the remaining not_run rows")
    parser.add_argument("--evaluate-only", action="store_true", help="No inference; recompute against current reviews")
    parser.add_argument("--batch-id", help="Existing batch to evaluate")
    args = parser.parse_args()
    if args.batch_id and not args.evaluate_only or args.limit and args.evaluate_only:
        parser.error("Use --batch-id only with --evaluate-only; --limit only with inference")
    root = args.root.resolve()
    batch_id = args.batch_id if args.evaluate_only else run_batch(root, limit=args.limit)["batch_id"]
    output = evaluate_batch(root, batch_id)
    if batch_id:
        folder = folder_for(root, batch_id)
        evaluation_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]
        path = folder / f"evaluation-{evaluation_id}.json"
        write_json(path, output)
        print(json.dumps({"evaluation_file": str(path), "diagnostics": output.get("diagnostics"),
                          "annotation_comparison": output.get("annotation_comparison")}, ensure_ascii=False))
    else:
        print(json.dumps(output, ensure_ascii=False))


if __name__ == "__main__":
    main()
