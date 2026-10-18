"""Small official-source acquisition pilot; current QA, never a historical prediction run."""

import argparse
import hashlib
import io
import json
import logging
import time
import urllib.error
import urllib.request
import urllib.robotparser
import uuid
from collections import Counter
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path
from urllib.parse import quote, urlsplit, urlunsplit

from pit_haf.data.evidence import EvidencePage, EvidenceVersion, version_id_for
from pit_haf.data.gateway import deliver_as_of
from pit_haf.data.snapshots import SnapshotStore

USER_AGENT = "PiTHAFResearchPilot/0.1 (local noncommercial research; sequential requests)"
MAX_BYTES = 64 * 1024 * 1024
MAX_CONFIGURED_BYTES = 128 * 1024 * 1024


def approved_url(url: str, allowed_hosts: set[str]) -> None:
    parsed = urlsplit(url)
    if (parsed.scheme != "https" or parsed.hostname not in allowed_hosts
            or parsed.username or parsed.password or parsed.port not in (None, 443)):
        raise ValueError("Acquisition URL/redirect outside explicit HTTPS source allowlist")


class ApprovedRedirect(urllib.request.HTTPRedirectHandler):
    def __init__(self, allowed_hosts: set[str]):
        self.allowed_hosts = allowed_hosts

    def redirect_request(self, request, fp, code, message, headers, newurl):
        approved_url(newurl, self.allowed_hosts)
        return super().redirect_request(request, fp, code, message, headers, newurl)


def fetch_public(url: str, allowed_hosts: set[str], *, timeout: float = 30,
                 max_bytes: int = MAX_BYTES) -> tuple[bytes, dict]:
    if type(max_bytes) is not int or not 1 <= max_bytes <= MAX_CONFIGURED_BYTES:
        raise ValueError("Configured response limit must be between 1 byte and 128 MiB")
    approved_url(url, allowed_hosts)
    opener = urllib.request.build_opener(ApprovedRedirect(allowed_hosts))
    parsed = urlsplit(url)
    transport_url = urlunsplit(parsed._replace(
        path=quote(parsed.path, safe="/%:@!$&'()*+,;=-._~"),
        query=quote(parsed.query, safe="%:@!$&'()*+,;=/?-._~"), fragment="",
    ))
    request = urllib.request.Request(transport_url, headers={"User-Agent": USER_AGENT})
    try:
        with opener.open(request, timeout=timeout) as response:
            if response.status != 200 or response.headers.get("Content-Range"):
                raise ValueError("Expected complete HTTP 200 response; partial content is not a snapshot")
            length = response.headers.get("Content-Length")
            if length and int(length) > max_bytes:
                raise ValueError("Response exceeds pilot byte limit")
            payload = response.read(max_bytes + 1)
            if len(payload) > max_bytes:
                raise ValueError("Response exceeds pilot byte limit")
            if length and len(payload) != int(length):
                raise ValueError("Response body length disagrees with Content-Length")
            return payload, {
                "source_url": url, "final_url": response.url, "http_status": response.status,
                "headers": dict(response.headers.items()), "retrieved_at": datetime.now(UTC).isoformat(),
            }
    except urllib.error.HTTPError as exc:
        # No retry with changed identity or browser bypass after denial.
        raise ValueError(f"HTTP {exc.code}: {url}") from exc


class PdfWarningCollector(logging.Handler):
    def __init__(self):
        super().__init__(logging.WARNING)
        self.page = None
        self.count = 0
        self.messages = []
        self.partial_pages = set()

    def emit(self, record):
        message = record.getMessage()
        self.count += 1
        if len(self.messages) < 300:
            self.messages.append({"page": self.page, "message": message[:2000]})
        if "skipped" in message.lower() or "exceeded" in message.lower():
            self.partial_pages.add(self.page)


def extract_pdf_pages(store: SnapshotStore, evidence: EvidenceVersion,
                      diagnostics: dict | None = None) -> tuple[EvidencePage, ...]:
    collector = PdfWarningCollector()
    logger = logging.getLogger("pypdf")
    if diagnostics is not None:
        logger.addHandler(collector)
    try:
        return _extract_pdf_pages(store, evidence, collector)
    finally:
        if diagnostics is not None:
            logger.removeHandler(collector)
        if diagnostics is not None:
            diagnostics.update(parser_warning_count=collector.count,
                               parser_warnings=collector.messages,
                               parser_warnings_truncated=collector.count > len(collector.messages),
                               potentially_partial_text_pages=sorted(
                                   page for page in collector.partial_pages if page is not None
                               ),
                               potentially_partial_document=None in collector.partial_pages)


def _extract_pdf_pages(store: SnapshotStore, evidence: EvidenceVersion,
                       collector: PdfWarningCollector) -> tuple[EvidencePage, ...]:
    from pypdf import PdfReader

    raw = store.read_blob(evidence.content_hash)
    if not raw.startswith(b"%PDF-"):
        raise ValueError("Downloaded response is not a PDF")
    reader = PdfReader(io.BytesIO(raw), strict=True)
    if reader.is_encrypted:
        raise ValueError("Encrypted PDF; no password/access-control bypass")
    if len(reader.pages) > 500:
        raise ValueError("PDF exceeds pilot page limit")
    pages = []
    for number, page in enumerate(reader.pages, start=1):
        collector.page = number
        text = page.extract_text() or ""
        pages.append(EvidencePage(
            record_id=evidence.record_id, version_id=evidence.version_id, ticker=evidence.ticker,
            content_hash=evidence.content_hash, page=number, text=text,
            text_hash=hashlib.sha256(text.encode()).hexdigest(), source_url=evidence.source_url,
            retrieved_at=evidence.retrieved_at, extractor=f"pypdf/{version('pypdf')};no_ocr",
            extraction_status="text_present" if text.strip() else "no_text_ocr_not_performed",
            data_kind=evidence.data_kind,
        ))
    return tuple(pages)


def validate_manifest_identity(evidence: EvidenceVersion, spec: dict) -> None:
    immutable = evidence.model_dump(mode="json")
    fields = {**spec, "data_kind": spec.get("data_kind", "real_document")}
    changed = [key for key, value in fields.items() if immutable.get(key) != value]
    if changed:
        raise ValueError("Manifest conflicts with immutable version metadata: " + ", ".join(changed))


def acquire_pilot(
    config: dict, *, store: SnapshotStore, output: Path, delay: float = 1,
    reuse_registered: bool = False, skip_registered: bool = False,
) -> dict:
    """Keep failures and quota shortfalls. Never infer times from file names or PDF signatures."""
    output.mkdir(parents=True, exist_ok=False)
    hosts = set(config["allowed_hosts"])
    documents = config["documents"]
    if reuse_registered:
        return reextract_registered(config, store=store, output=output)
    ids = [item["record_id"] for item in documents]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate record_id in acquisition manifest")
    json_config = json.dumps(config, ensure_ascii=False, sort_keys=True).encode()
    (output / "sources.json").write_bytes(json_config)
    resources = {}
    robot_policies = {}
    events = []

    def acquire_resource(url: str, kind: str) -> dict:
        if url in resources:
            return resources[url]
        entry = {"url": url, "kind": kind}
        try:
            payload, metadata = fetch_public(url, hosts)
            entry.update(metadata, status="downloaded", content_hash=store.put_blob(payload))
            if kind == "robots":
                policy = urllib.robotparser.RobotFileParser(url)
                policy.parse(payload.decode("utf-8", errors="replace").splitlines())
                robot_policies[urlsplit(url).hostname] = policy
        except (OSError, ValueError) as exc:
            entry.update(status="failed", error=str(exc), retrieved_at=datetime.now(UTC).isoformat())
        store.log_acquisition(entry)
        resources[url] = entry
        time.sleep(delay)
        return entry

    # Read source policies once. Unknown/403 robots is recorded; no bypass or bulk crawling.
    for host in sorted(hosts):
        acquire_resource(f"https://{host}/robots.txt", "robots")
    for source in config["sources"]:
        for key, kind in (("listing_url", "listing"), ("rights_url", "rights")):
            if source.get(key):
                acquire_resource(source[key], kind)

    existing = {item.version_id: item for item in store.versions()}
    existing_records = {}
    for item in existing.values():
        existing_records.setdefault(item.record_id, []).append(item)
    pages_path = output / "pages.jsonl"
    with pages_path.open("x", encoding="utf-8", newline="\n") as stream:
        for spec in documents:
            event = {"record_id": spec["record_id"], "ticker": spec["ticker"],
                     "source_url": spec["source_url"], "status": "failed"}
            diagnostics = {}
            try:
                host = urlsplit(spec["source_url"]).hostname
                robot = robot_policies.get(host)
                if robot and not robot.can_fetch(USER_AGENT, spec["source_url"]):
                    raise ValueError("robots.txt disallows configured URL")
                prior = existing_records.get(spec["record_id"], []) if skip_registered else []
                if prior:
                    if len(prior) != 1:
                        raise ValueError("Local reuse needs exactly one version; select revisions explicitly")
                    evidence = prior[0]
                    validate_manifest_identity(evidence, spec)
                    store.read_blob(evidence.content_hash)
                    event.update(registration="local_reuse_without_remote_revalidation",
                                 content_hash=evidence.content_hash, network_requests=0)
                else:
                    options = ({"max_bytes": config["max_document_bytes"]}
                               if "max_document_bytes" in config else {})
                    payload, acquisition = fetch_public(spec["source_url"], hosts, **options)
                    event.update(acquisition)
                    digest = store.put_blob(payload)
                    event["content_hash"] = digest
                    if not payload.startswith(b"%PDF-"):
                        raise ValueError("Response is not a PDF; retained for acquisition audit only")
                    listing = resources.get(spec.get("listing_url"), {})
                    version_id = version_id_for(spec["record_id"], digest)
                    if version_id in existing:
                        evidence = existing[version_id]
                        validate_manifest_identity(evidence, spec)
                        event["registration"] = "existing_version_first_observation_preserved"
                    else:
                        evidence = EvidenceVersion(
                            **spec, version_id=version_id, content_hash=digest,
                            retrieved_at=acquisition["retrieved_at"], system_recorded_at=datetime.now(UTC),
                            listing_snapshot_hash=listing.get("content_hash"),
                        )
                        store.register(evidence)
                        existing[version_id] = evidence
                        event["registration"] = "new_version"
                event["version_id"] = evidence.version_id
                pages = extract_pdf_pages(store, evidence, diagnostics)
                event.update(diagnostics)
                for page in pages:
                    stream.write(page.model_dump_json() + "\n")
                event.update(
                    status="extracted", pages=len(pages),
                    text_pages=sum(page.extraction_status == "text_present" for page in pages),
                    empty_pages=sum(
                        page.extraction_status == "no_text_ocr_not_performed" for page in pages
                    ),
                    historical_eligibility="quarantined_no_time_or_revision_proof",
                )
            except Exception as exc:
                # Per-document acquisition failures must remain visible in the denominator.
                event.update(error_type=type(exc).__name__, error=str(exc))
            event.update(diagnostics)
            events.append(event)
            store.log_acquisition(event)
            time.sleep(delay)
    cutoff = datetime.now(UTC).isoformat()
    strict = deliver_as_of(store, decision_at=cutoff)
    successes = Counter(event["ticker"] for event in events if event["status"] == "extracted")
    summary = {
        "run_kind": ("real_document_acquisition_and_current_text_qa" if all(
            item.get("data_kind", "real_document") == "real_document" for item in documents
        ) else "test_fixture"),
        "research_prediction_results": False, "historical_availability_inferred": False,
        "skip_registered_without_remote_revalidation": skip_registered,
        "max_document_bytes": config.get("max_document_bytes", MAX_BYTES),
        "created_at": cutoff, "manifest_hash": hashlib.sha256(json_config).hexdigest(),
        "target_documents": config.get("target_documents", 24),
        "configured_documents": len(documents), "success_documents": sum(successes.values()),
        "success_by_ticker": dict(successes), "failed_documents": len(documents)-sum(successes.values()),
        "target_shortfall": max(0, config.get("target_documents", 24)-sum(successes.values())),
        "page_count": sum(event.get("pages", 0) for event in events),
        "text_page_count": sum(event.get("text_pages", 0) for event in events),
        "empty_page_count_no_ocr": sum(event.get("empty_pages", 0) for event in events),
        "strict_gateway_deliveries": len(strict.deliveries), "strict_audit": list(strict.audit),
        "pages_file": str(pages_path.resolve()),
        "pages_sha256": hashlib.sha256(pages_path.read_bytes()).hexdigest(),
        "resources": list(resources.values()), "documents": events,
        "limitations": [
            "No OCR or human numeric/semantic gold completed by this command.",
            "Downloaded bytes observed today do not prove any historical revision/time.",
            "No raw redistribution rights granted by this acquisition command.",
            "Successful extraction alone does not imply text/table fidelity.",
        ],
    }
    publish_summary(output, summary)
    return summary


def reextract_registered(config: dict, *, store: SnapshotStore, output: Path) -> dict:
    """Export registered snapshots with no network; preserves all earlier acquisition attempts."""
    specs = {item["record_id"]: item for item in config["documents"]}
    ids = set(specs)
    raw_config = json.dumps(config, ensure_ascii=False, sort_keys=True).encode()
    (output / "sources.json").write_bytes(raw_config)
    events = []
    pages_file = output / "pages.jsonl"
    with pages_file.open("x", encoding="utf-8", newline="\n") as stream:
        for item in store.versions():
            if item.record_id not in ids:
                continue
            event = {"record_id": item.record_id, "version_id": item.version_id,
                     "ticker": item.ticker, "content_hash": item.content_hash}
            diagnostics = {}
            try:
                validate_manifest_identity(item, specs[item.record_id])
                pages = extract_pdf_pages(store, item, diagnostics)
                event.update(diagnostics)
                for page in pages:
                    stream.write(page.model_dump_json() + "\n")
                event.update(status="extracted", pages=len(pages), text_pages=sum(
                    page.extraction_status == "text_present" for page in pages
                ))
            except Exception as exc:
                event.update(status="failed", error_type=type(exc).__name__, error=str(exc))
            event.update(diagnostics)
            events.append(event)
    successful = [event for event in events if event["status"] == "extracted"]
    cutoff = datetime.now(UTC).isoformat()
    summary = {
        "run_kind": ("real_document_snapshot_reextraction" if all(
            item.get("data_kind", "real_document") == "real_document" for item in config["documents"]
        ) else "test_fixture"),
        "network_requests": 0, "research_prediction_results": False,
        "manifest_hash": hashlib.sha256(raw_config).hexdigest(),
        "created_at": cutoff, "target_documents": config.get("target_documents", 24),
        "configured_documents": len(ids), "registered_versions": len(events),
        "success_documents": len({event["record_id"] for event in successful}),
        "success_by_ticker": dict(Counter(event["ticker"] for event in successful)),
        "failed_documents": sum(event["status"] == "failed" for event in events),
        "configured_records_not_registered": sorted(ids - {event["record_id"] for event in events}),
        "target_shortfall": max(0, config.get("target_documents", 24)-len({
            event["record_id"] for event in successful
        })),
        "page_count": sum(event.get("pages", 0) for event in events),
        "text_page_count": sum(event.get("text_pages", 0) for event in events),
        "empty_page_count_no_ocr": sum(
            event.get("pages", 0)-event.get("text_pages", 0) for event in events
        ),
        "strict_gateway_deliveries": len(deliver_as_of(store, decision_at=cutoff).deliveries),
        "pages_file": str(pages_file.resolve()),
        "pages_sha256": hashlib.sha256(pages_file.read_bytes()).hexdigest(), "documents": events,
        "limitations": ["Re-extraction does not create historical time/version proof.",
                        "No OCR or human semantic/numeric QA performed by this command."],
    }
    publish_summary(output, summary)
    return summary


def publish_summary(output: Path, summary: dict) -> None:
    """Readers see the completed release, never a partially written JSON summary."""
    temporary = output / "summary.json.tmp"
    temporary.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(output / "summary.json")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sources", type=Path, default=Path("configs/pilot_sources.json"))
    parser.add_argument("--root", type=Path, default=Path("data/cache/evidence"))
    parser.add_argument("--output", type=Path)
    parser.add_argument("--extract-existing", action="store_true", help="No network; export snapshots")
    parser.add_argument("--skip-registered", action="store_true",
                        help="Reuse unique local versions without checking for remote revisions")
    args = parser.parse_args()
    run_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]
    output = args.output or Path("outputs/milestone-1/data-pilot") / run_id
    config = json.loads(args.sources.read_text(encoding="utf-8"))
    result = acquire_pilot(config, store=SnapshotStore(args.root), output=output,
                           reuse_registered=args.extract_existing,
                           skip_registered=args.skip_registered)
    print(json.dumps({key: result[key] for key in (
        "success_documents", "success_by_ticker", "failed_documents", "target_shortfall",
        "page_count", "text_page_count", "strict_gateway_deliveries", "pages_file"
    )}, indent=2))


if __name__ == "__main__":
    main()
