"""Audit frozen extraction outputs with whitespace-only source mapping; no inference."""

import argparse
import json
import uuid
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

from pit_haf.llm.ollama import Extraction, sha256, write_json
from pit_haf.llm.pilot import check_output, load_cases, number_supported
from pit_haf.verification.quotes import normalized_space, resolve_quote


def audit_run(source: Path, output_base: Path) -> Path:
    manifest_bytes = (source / "manifest.json").read_bytes()
    manifest = json.loads(manifest_bytes)
    if manifest.get("status") != "completed" or not manifest.get("model_digest_stable"):
        raise ValueError("Require a completed run with stable model identity")
    cases_path = source / "cases.jsonl"
    if sha256(cases_path.read_bytes()) != manifest["input_cases_sha256"]:
        raise ValueError("Case snapshot checksum mismatch")
    cases = load_cases(cases_path, smoke=manifest["run_kind"] == "smoke_fixture")
    results_bytes = (source / "results.jsonl").read_bytes()
    results = [json.loads(line) for line in results_bytes.splitlines() if line.strip()]
    if len(cases) != len(results):
        raise ValueError("Case/result count mismatch")
    audits = []
    for index, (case, row) in enumerate(zip(cases, results, strict=True), 1):
        if case.sample_id != row["sample_id"]:
            raise ValueError("Case/result identity mismatch")
        generation = row["generation"]
        output = generation["output"]
        if output is not None:
            successful = [(i, item) for i, item in enumerate(generation["attempts"], 1)
                          if item["status"] == "schema_valid"]
            if len(successful) != 1:
                raise ValueError("Require exactly one successful raw attempt")
            attempt_number, attempt = successful[0]
            directory = source / "samples" / f"{index:04d}" / f"attempt-{attempt_number:02d}"
            raw = (directory / "response.raw").read_bytes()
            request = (directory / "request.json").read_bytes()
            if sha256(raw) != attempt["response_sha256"] or sha256(request) != attempt["request_sha256"]:
                raise ValueError("Raw attempt checksum mismatch")
            parsed = Extraction.model_validate_json(json.loads(raw)["message"]["content"])
            if parsed.model_dump() != output:
                raise ValueError("Scored output differs from the preserved raw response")
            sent = json.loads(json.loads(request)["messages"][1]["content"])
            if sent["context"] != case.context or sent["record_id"] != case.record_id:
                raise ValueError("Case context differs from the preserved request")
        strict = check_output(case, output)
        resolution = resolve_quote(case.context, output["quote"] if output else "")
        mapped = resolution.mode in {"exact", "whitespace_mapped"}
        numeric = bool(output) and mapped and all(
            number_supported(normalized_space(value), normalized_space(resolution.source_quote))
            for value in output["extracted_numbers"]
        )
        accepted = bool(output) and mapped and numeric and not output["insufficient_evidence"]
        audits.append({"sample_id": case.sample_id, "data_kind": case.data_kind,
                       "source_content_hash": case.content_hash, "page": case.page,
                       "strict_accepted": strict["accepted"], "resolution": resolution.as_dict(),
                       "mapped_numbers_supported": numeric, "mapped_accepted": accepted,
                       "semantic_claim_support": "not_assessed", "numeric_gold": "not_assessed"})
    run_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]
    destination = output_base / run_id
    destination.mkdir(parents=True, exist_ok=False)
    write_json(destination / "audit.json", audits)
    write_json(destination / "summary.json", {
        "run_kind": "offline_quote_verifier_replay", "source_run_kind": manifest["run_kind"],
        "new_inference_calls": 0, "research_prediction_results": False,
        "policy": "unique_exact_or_whitespace_mapped_v0.1", "sample_denominator": len(audits),
        "source_run": str(source.resolve()), "source_manifest_sha256": sha256(manifest_bytes),
        "source_results_sha256": sha256(results_bytes),
        "strict_accepted": sum(x["strict_accepted"] for x in audits),
        "mapped_accepted": sum(x["mapped_accepted"] for x in audits),
        "resolution_counts": dict(Counter(x["resolution"]["mode"] for x in audits)),
        "raw_model_outputs_unchanged": True,
        "limitations": ["Offsets refer to supplied context; page offsets require selection audit.",
                        "Whitespace mapping is source resolution, not new model performance.",
                        "Spelling/numbers/signs/omissions are never repaired or fuzzy matched.",
                        "Semantic support, numeric gold and historical availability are not assessed."],
    })
    return destination


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-run", required=True, type=Path)
    parser.add_argument("--output-dir", type=Path, default=Path("outputs/quote-replay"))
    args = parser.parse_args()
    destination = audit_run(args.source_run, args.output_dir)
    print(f"Offline quote audit: {destination}")


if __name__ == "__main__":
    main()
