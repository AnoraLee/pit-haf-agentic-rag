"""Read-only assistant source audit, separate from the declared human review ledger."""

import argparse
import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from pit_haf.data.catalog import Catalog
from pit_haf.data.hub import file_sha
from pit_haf.llm.ollama import write_json
from pit_haf.research.evaluation import checked_report, load_batch
from pit_haf.research.reviews import active_pack

LOCATION = Path("data/development/source-audit-v0.1")
REPORT = Path("docs/research/development-source-audit-v0.1.md")
Text = Annotated[str, Field(min_length=1)]
VERDICTS = {
    "useful_claims": "Có nhận định hữu ích, có cơ sở",
    "accepted_partial": "Có trích dẫn nhưng trả lời chưa đầy đủ/đúng trọng tâm",
    "accepted_misleading": "Có trích dẫn nhưng dễ hiểu sai kỳ hoặc điều kiện",
    "context_gap": "Thiếu ngữ cảnh; từ chối phù hợp",
    "no_answer_partial_context": "Không có đáp án; ngữ cảnh mới hỗ trợ một phần",
    "blocked_error": "Bản nháp có sai sót đã bị chặn",
    "unnecessary_abstention": "Bỏ sót bằng chứng có thể dùng",
    "technical_failure": "Lỗi sinh đầu ra",
}
CONTEXTS = {"sufficient": "Đủ để trả lời", "partial": "Hỗ trợ một phần", "insufficient": "Thiếu/sai chủ đề"}


class CitationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    page: int = Field(ge=1)
    terms: list[Text] = Field(min_length=1, max_length=16)


class AuditAnswer(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    case_id: Text
    answer: Text
    context_status: Literal["sufficient", "partial", "insufficient"]
    context_note: Text
    verdict: Literal["useful_claims", "accepted_partial", "accepted_misleading", "context_gap",
                     "no_answer_partial_context", "blocked_error", "unnecessary_abstention", "technical_failure"]
    model_note: Text
    references: list[CitationRequest] = Field(min_length=1, max_length=5)


class AuditSpec(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    provenance: Literal["assistant_source_audit"]
    independent_human_gold: Literal[False]
    batch_id: str = Field(pattern=r"^\d{8}T\d{6}Z-[0-9a-f]{8}$")
    method: Text
    rows: list[AuditAnswer] = Field(min_length=1)


def assemble(root, spec, created_at):
    """Rebind every answer to the sealed cases, original run and exact PDF page text.

    Literal anchors and byte hashes establish provenance, not semantic correctness.
    Answer meaning and visual table interpretation remain assistant judgements.
    """
    index, cases = active_pack(root)
    if [r.case_id for r in spec.rows] != list(cases):
        raise ValueError("Audit must cover every published case once, in published order")
    batch = load_batch(root, spec.batch_id)
    if (batch["pack_id"] != index["pack_id"] or batch["cases_sha256"] != index["cases_sha256"] or
            [r["case_id"] for r in batch["cases"]] != list(cases)):
        raise ValueError("Audit batch differs from the active source pack")
    pack = root / "outputs/development-cases" / index["pack_id"]
    summary = json.loads((pack / "summary.json").read_text(encoding="utf-8"))
    snapshot = (root / summary["snapshot"]).resolve()
    if not snapshot.is_relative_to((root / "outputs/milestone-1/data-pilot").resolve()):
        raise ValueError("Invalid pinned audit catalog location")
    catalog = Catalog(root, snapshot)
    if any(catalog.pointer[k] != summary[k] for k in ("summary_sha256", "catalog_sha256")):
        raise ValueError("Audit catalog differs from the pinned snapshot")
    page_cache, rows = {}, []
    for answer, run in zip(spec.rows, batch["cases"], strict=True):
        case = cases[answer.case_id]
        report = checked_report(root, run, case, batch)
        versions = {s["passage"]["version_id"] for s in case["evidence"]}
        if len(versions) != 1:
            raise ValueError("This audit requires one issuer PDF per case")
        version_id = next(iter(versions))
        citations = []
        for ref in answer.references:
            key = (version_id, ref.page)
            if key not in page_cache:
                page_cache[key] = catalog.page(*key)
            version, page, _ = page_cache[key]
            if (version.ticker != case["ticker"] or version.media_type != "application/pdf" or
                    version.reporting_period != case["retrieval_scope"]["reporting_period"] or
                    page.version_id != version_id or page.content_hash != version.content_hash or
                    page.ticker != version.ticker or page.record_id != version.record_id or
                    page.source_url != version.source_url):
                raise ValueError("Audit page identity/period differs from the case issuer PDF")
            spans = []
            for term in ref.terms:
                offset = page.text.find(term)
                if offset < 0:
                    raise ValueError(f"Audit anchor missing: {answer.case_id}, page {ref.page}, {term!r}")
                # Keep nearby labels where possible; the complete linked page is authoritative.
                start, end = max(0, offset - 75), min(len(page.text), offset + len(term) + 75)
                spans.append({"anchor": term, "start": start, "end": end, "quote": page.text[start:end]})
            citations.append({"version_id": version_id, "page": ref.page, "page_text_sha256": page.text_hash,
                              "content_sha256": version.content_hash, "source_url": version.source_url,
                              "pdf_url": f"/api/documents/{version_id}/raw#page={ref.page}", "spans": spans})
        rows.append({**answer.model_dump(exclude={"references"}), "ticker": case["ticker"],
                     "question": case["question"], "run_id": run["run_id"], "report_sha256": run["report_sha256"],
                     "original_status": report["status"], "accepted_claims": len(report["claims"]),
                     "rejected_claims": len(report["rejected_claims"]), "citations": citations})
    return {"schema_version": 1, "provenance": spec.provenance, "independent_human_gold": False,
            "semantic_accuracy": None, "historical_availability_validated": False,
            "method": spec.method, "created_at": created_at, "pack_id": index["pack_id"],
            "cases_sha256": index["cases_sha256"], "batch_id": spec.batch_id,
            "batch_manifest_sha256": file_sha(root / "outputs/development-batches" / spec.batch_id / "manifest.json"),
            "answers_sha256": file_sha(root / LOCATION / "answers.json"),
            "summary": {"answered_cases": len(rows), "context_counts": dict(Counter(r["context_status"] for r in rows)),
                        "verdict_counts": dict(Counter(r["verdict"] for r in rows))},
            "context_labels": CONTEXTS, "verdict_labels": VERDICTS, "rows": rows}


def render_markdown(audit):
    lines = ["# Đối chiếu nguồn 24 câu hỏi phát triển", "", audit["method"], "",
             "**Nguồn gốc: trợ lý soạn; chưa được người dùng xác nhận độc lập.** "
             "Không thay đổi sổ đáp án tham chiếu thủ công hoặc tính độ chính xác ngữ nghĩa từ bản này.", "",
             f"Bộ câu hỏi: `{audit['pack_id']}`. Bản chạy gốc: `{audit['batch_id']}`.", "",
             "Số trang dưới đây là trang PDF (bắt đầu từ 1), có thể khác số in trên tài liệu. "
             "Các mục tiêu 2025 là kế hoạch nêu trong báo cáo 2024. "
             "Kiểm tra nguồn này không xác nhận tính sẵn có tại thời điểm lịch sử (PiT).", "",
             "## Nhận xét về hệ thống", ""]
    for key, count in audit["summary"]["verdict_counts"].items():
        lines.append(f"- {VERDICTS[key]}: {count} câu.")
    lines.extend(["", "Đây là phân loại định tính của trợ lý, không phải tỷ lệ đúng trên bộ kiểm thử độc lập. "
                  "Bộ kiểm tra nguyên văn/số liệu có thể chặn số đúng khi năm/đơn vị ở ngoài câu trích; "
                  "đồng thời trích dẫn hợp lệ vẫn có thể sai trọng tâm hoặc nhầm kế hoạch với thực hiện.", ""])
    for number, row in enumerate(audit["rows"], 1):
        lines.extend([f"## {number}. {row['ticker']} — {row['question']}", "", row["answer"], "",
                      f"**Ngữ cảnh model:** {CONTEXTS[row['context_status']]}. {row['context_note']}", "",
                      f"**Đối chiếu kết quả:** {VERDICTS[row['verdict']]}. {row['model_note']}", ""])
        refs = []
        for cite in row["citations"]:
            blob = "../../data/cache/evidence/blobs/" + cite["content_sha256"][:2] + "/" + cite["content_sha256"]
            refs.append(f"[trang PDF {cite['page']}]({blob}#page={cite['page']})")
        lines.extend(["Nguồn: " + ", ".join(refs) + ".", "",
                      f"Case `{row['case_id']}` · Run `{row['run_id']}` · "
                      f"{row['accepted_claims']} nhận định qua kiểm tra, {row['rejected_claims']} bị chặn.", ""])
    return "\n".join(lines)


def publish(root):
    folder = root / LOCATION
    spec = AuditSpec.model_validate_json((folder / "answers.json").read_bytes())
    audit = assemble(root, spec, datetime.now(UTC).isoformat())
    write_json(folder / "audit.json", audit)
    (root / REPORT).parent.mkdir(parents=True, exist_ok=True)
    (root / REPORT).write_text(render_markdown(audit), encoding="utf-8")
    write_json(folder / "integrity.json", {"audit_sha256": file_sha(folder / "audit.json"),
                                          "report_sha256": file_sha(root / REPORT)})
    return audit


def load_source_audit(root):
    folder = root / LOCATION
    if not folder.exists():
        return None
    seal = json.loads((folder / "integrity.json").read_text(encoding="utf-8"))
    if file_sha(folder / "audit.json") != seal["audit_sha256"] or file_sha(root / REPORT) != seal["report_sha256"]:
        raise ValueError("Assistant audit artifact checksum mismatch")
    audit = json.loads((folder / "audit.json").read_text(encoding="utf-8"))
    spec = AuditSpec.model_validate_json((folder / "answers.json").read_bytes())
    if assemble(root, spec, audit["created_at"]) != audit:
        raise ValueError("Assistant audit sources, answers or original run changed")
    return audit


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--publish", action="store_true", help="Seal authored answers locally; no inference or review writes")
    args = parser.parse_args()
    audit = publish(args.root.resolve()) if args.publish else load_source_audit(args.root.resolve())
    print(json.dumps(audit["summary"] if audit else {"available": False}, ensure_ascii=False))


if __name__ == "__main__":
    main()
