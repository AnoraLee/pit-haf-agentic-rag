"""Read real local artifacts; retrieve literal passages before bounded local extraction."""

import json
import math
import re
import unicodedata
import uuid
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

from pit_haf.data.evidence import EvidencePage, EvidenceVersion
from pit_haf.data.snapshots import SnapshotError, SnapshotStore
from pit_haf.llm.ollama import ModelInspectionError, OllamaAdapter, OllamaConfig, sha256, write_json
from pit_haf.llm.pilot import PilotCase, build_messages, number_supported
from pit_haf.verification.quotes import normalized_space, resolve_quote


@dataclass(frozen=True)
class Corpus:
    versions: tuple[EvidenceVersion, ...] = ()
    pages: tuple[EvidencePage, ...] = ()
    errors: tuple[str, ...] = ()
    snapshot: str | None = None


@dataclass(frozen=True)
class Passage:
    version_id: str
    record_id: str
    ticker: str
    page: int
    start: int
    end: int
    text: str
    page_text_hash: str
    score: float


def workspace_fingerprint(root: Path) -> tuple:
    """Invalidate UI caches when local artifacts change, including raw source bytes."""
    paths = [root / "data/cache/evidence/registry.sqlite3"]
    for pattern in (
        "outputs/milestone-1/data-pilot/*/summary.json",
        "outputs/milestone-1/data-pilot/*/pages.jsonl",
        "outputs/llm-pilot/*/manifest.json", "outputs/llm-pilot/*/metrics.json",
        "outputs/quote-replay/*/summary.json", "data/cache/evidence/blobs/*/*",
    ):
        paths.extend(root.glob(pattern))
    return tuple((str(path.relative_to(root)), path.stat().st_mtime_ns, path.stat().st_size)
                 for path in sorted(set(paths)) if path.is_file())


def load_corpus(root: Path) -> Corpus:
    candidates = sorted(root.glob("outputs/milestone-1/data-pilot/*/summary.json"),
                        key=lambda path: path.stat().st_mtime_ns, reverse=True)
    if not candidates or not (root / "data/cache/evidence/registry.sqlite3").is_file():
        return Corpus(errors=("Chưa có snapshot tài liệu trên máy. Chạy pilot-data trước.",))
    summary_path = candidates[0]
    try:
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        pages_raw = (summary_path.parent / "pages.jsonl").read_bytes()
        if sha256(pages_raw) != summary["pages_sha256"]:
            raise SnapshotError("Checksum tập trang không khớp snapshot.")
        store = SnapshotStore(root / "data/cache/evidence")
        versions = tuple(item for item in store.versions() if item.data_kind == "real_document")
        by_id = {item.version_id: item for item in versions}
        for item in versions:
            store.read_blob(item.content_hash)
        pages, seen = [], set()
        for line in pages_raw.splitlines():
            if not line.strip():
                continue
            page = EvidencePage.model_validate_json(line)
            version = by_id.get(page.version_id)
            if version is None or page.data_kind != "real_document" or (
                page.record_id, page.ticker, page.content_hash, page.source_url
            ) != (version.record_id, version.ticker, version.content_hash, version.source_url):
                raise SnapshotError("Trang không khớp định danh tài liệu trong registry.")
            if sha256(page.text.encode()) != page.text_hash:
                raise SnapshotError("Checksum văn bản trang không khớp.")
            identity = (page.version_id, page.page)
            if identity in seen:
                raise SnapshotError("Trùng trang trong snapshot.")
            seen.add(identity)
            pages.append(page)
        if len(pages) != summary["page_count"] or {p.version_id for p in pages} != set(by_id):
            raise SnapshotError("Coverage trang và registry không khớp; hãy trích xuất lại.")
        return Corpus(versions, tuple(pages), snapshot=str(summary_path.relative_to(root)))
    except (OSError, ValueError, KeyError, TypeError) as exc:
        return Corpus(errors=(f"Không mở được kho bằng chứng: {exc}",))


def load_pilot_metrics(root: Path) -> dict:
    """Show a completed real pilot only; never substitute fixtures or fabricated metrics."""
    candidates = sorted(root.glob("outputs/llm-pilot/*/manifest.json"),
                        key=lambda path: path.stat().st_mtime_ns, reverse=True)
    for path in candidates:
        try:
            manifest = json.loads(path.read_text(encoding="utf-8"))
            if manifest.get("status") != "completed" or not manifest.get("model_digest_stable"):
                continue
            if manifest.get("run_kind") != "real_document_extraction_pilot":
                continue
            metrics = json.loads((path.parent / "metrics.json").read_text(encoding="utf-8"))
            rows = [json.loads(line) for line in (path.parent / "results.jsonl").read_bytes()
                    .splitlines() if line.strip()]
            result = {"manifest": manifest, "metrics": metrics,
                      "document_count": len({row["record_id"] for row in rows}),
                      "path": str(path.parent.relative_to(root)), "replay": None}
            for replay_path in sorted(root.glob("outputs/quote-replay/*/summary.json"),
                                      key=lambda p: p.stat().st_mtime_ns, reverse=True):
                replay = json.loads(replay_path.read_text(encoding="utf-8"))
                if (replay.get("source_manifest_sha256") == sha256(path.read_bytes())
                    and replay.get("source_results_sha256") == sha256(
                        (path.parent / "results.jsonl").read_bytes()
                    ) and replay.get("source_run_kind") == manifest["run_kind"]):
                    result["replay"] = replay
                    break
            return result
        except (OSError, ValueError, KeyError, TypeError):
            continue
    return {}


def tokens(text: str) -> list[str]:
    normalized = unicodedata.normalize("NFD", text.lower().replace("đ", "d"))
    normalized = "".join(char for char in normalized if not unicodedata.combining(char))
    return re.findall(r"[a-z0-9]+", normalized)


def search_passages(corpus: Corpus, query: str, *, ticker: str | None = None,
                    allowed_versions: set[str] | None = None, limit: int = 6) -> list[Passage]:
    """BM25 dev baseline. Gate first: blocked/future text never enters corpus statistics.

    None means explicitly exploratory current-document reading; an empty set means
    the historical gateway delivered no evidence. Scores are relevance, not confidence.
    Offsets refer to exact Python characters of the retained extracted page text.
    """
    query_tokens = set(tokens(query))
    if not query_tokens or limit < 1:
        return []
    chunks = []
    for page in corpus.pages:
        if ticker and page.ticker != ticker:
            continue
        if allowed_versions is not None and page.version_id not in allowed_versions:
            continue
        start = 0
        while start < len(page.text):
            end = min(start + 900, len(page.text))
            if end < len(page.text):
                boundary = page.text.rfind(" ", start + 500, end)
                if boundary > start:
                    end = boundary
            text = page.text[start:end]
            counts = Counter(tokens(text))
            if counts:
                chunks.append((page, start, end, text, counts))
            if end == len(page.text):
                break
            start = max(start + 1, end - 120)
    if not chunks:
        return []
    average = sum(sum(row[4].values()) for row in chunks) / len(chunks)
    frequency = Counter(term for row in chunks for term in query_tokens if term in row[4])
    ranked = []
    for page, start, end, text, counts in chunks:
        score = 0.0
        length = sum(counts.values())
        for term in query_tokens:
            count = counts[term]
            if count:
                inverse = math.log(1 + (len(chunks) - frequency[term] + .5)
                                   / (frequency[term] + .5))
                score += inverse * count * 2.2 / (count + 1.2 * (.25 + .75 * length / average))
        if score:
            ranked.append(Passage(page.version_id, page.record_id, page.ticker, page.page,
                                  start, end, text, page.text_hash, score))
    return sorted(ranked, key=lambda row: (-row.score, row.record_id, row.page, row.start))[:limit]


def extract_passage(corpus: Corpus, passage: Passage, output_base: Path, *, mode: str,
                    decision_at: str | None = None, allowed_versions: set[str] | None = None,
                    retrieval: dict | None = None, adapter=None) -> dict:
    """Persist source/model/request/raw output/verifier, including unsuccessful calls."""
    if mode not in {"exploratory_current", "strict_point_in_time"}:
        raise ValueError("Unknown analysis mode")
    if mode == "strict_point_in_time" and (
        not decision_at or allowed_versions is None or passage.version_id not in allowed_versions
    ):
        raise ValueError("Historical analysis requires a gateway-delivered version and cutoff")
    version = next(item for item in corpus.versions if item.version_id == passage.version_id)
    page = next(item for item in corpus.pages if item.version_id == passage.version_id
                and item.page == passage.page)
    if (page.text_hash != passage.page_text_hash or passage.start < 0
        or passage.end <= passage.start or passage.end > len(page.text)
        or page.text[passage.start:passage.end] != passage.text):
        raise ValueError("Selected passage differs from its source snapshot")
    run_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]
    destination = output_base / run_id
    destination.mkdir(parents=True, exist_ok=False)
    config = OllamaConfig(max_retries=0)
    client = adapter or OllamaAdapter(config)
    case = PilotCase(
        sample_id=run_id, data_kind="real_document", ticker=version.ticker,
        record_id=version.record_id, version_id=version.version_id,
        content_hash=version.content_hash, source_url=version.source_url, page=passage.page,
        context=passage.text, expected_quote="",
    )
    result = {
        "run_id": run_id, "created_at": datetime.now(UTC).isoformat(),
        "run_kind": "interactive_document_extraction", "mode": mode, "decision_at": decision_at,
        "status": "started", "config": config.model_dump(), "source": version.model_dump(mode="json"),
        "passage": asdict(passage), "context_sha256": sha256(passage.text.encode()),
        "corpus_snapshot": corpus.snapshot, "retrieval_audit": retrieval,
        "semantic_support": "not_assessed", "research_prediction_results": False,
        "historical_availability_validated": mode == "strict_point_in_time",
        "path": str(destination.resolve()), "generation": None,
    }
    write_json(destination / "analysis.json", result)
    try:
        before = client.inspect(destination / "model-before")
        result["model_before"] = before
        generation = client.extract(build_messages(case), destination / "generation")
        result["generation"] = generation
        after = client.inspect(destination / "model-after")
        result["model_after"] = after
        stable = before["digest"] == after["digest"]
        result["model_digest_stable"] = stable
        output = generation["output"]
        resolution = resolve_quote(passage.text, output["quote"] if output else "")
        numeric = bool(output) and resolution.mode in {"exact", "whitespace_mapped"} and all(
            number_supported(normalized_space(value), normalized_space(resolution.source_quote))
            for value in output["extracted_numbers"]
        )
        accepted = bool(output) and stable and numeric and not output["insufficient_evidence"]
        result["verification"] = {
            "accepted_literal_evidence": accepted, "quote": resolution.as_dict(),
            "numbers_supported": numeric, "semantic_support": "not_assessed",
            "page_start": passage.start + resolution.start if resolution.start is not None else None,
            "page_end": passage.start + resolution.end if resolution.end is not None else None,
        }
        reasons = []
        if not output:
            reasons.append("generation_failed")
        elif output["insufficient_evidence"]:
            reasons.append("model_abstained")
        if not stable:
            reasons.append("model_changed")
        if resolution.mode not in {"exact", "whitespace_mapped"}:
            reasons.append("quote_" + resolution.mode)
        elif not numeric:
            reasons.append("numbers_not_supported")
        result["block_reasons"] = reasons
        result["status"] = "verified_quote" if accepted else "blocked"
    except (ModelInspectionError, OSError, ValueError) as exc:
        result.update({"status": "failed", "error": str(exc)})
    finally:
        write_json(destination / "analysis.json", result)
    return result
