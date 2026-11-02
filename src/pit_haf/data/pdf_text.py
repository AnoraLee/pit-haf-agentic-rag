"""Opt-in, bounded alternate PDF text for section retrieval; original catalog stays intact."""

import io
import json

import pdfplumber

from pit_haf.data.evidence import EvidencePage
from pit_haf.data.financial_sections import load_profile, search_financial, topic_for
from pit_haf.data.hub import file_sha
from pit_haf.data.table_page_policy import POLICY as PAGE_POLICY
from pit_haf.data.table_page_policy import gate, load_policy
from pit_haf.llm.ollama import sha256
from pit_haf.ui.workspace import Corpus

PROFILE = "configs/pdf_text_v0_7.json"


def settings(root):
    p = json.loads((root / PROFILE).read_text(encoding="utf-8"))
    if (p["profile_id"] != "financial_pdf_text_v0.7" or p["status"] != "development_not_frozen" or
            p["max_reparsed_pages"] != 400 or p["pdfplumber_version"] != pdfplumber.__version__ or
            p["extractor"] != "pdfplumber_text_v0.7" or p["ocr_performed"] is not False):
        raise ValueError("Unknown PDF text profile/version/budget")
    return p


def extract_text_pages(payload, content_hash, *, max_pages, numbers=None):
    if sha256(payload) != content_hash:
        raise ValueError("Alternate PDF text raw checksum mismatch")
    with pdfplumber.open(io.BytesIO(payload)) as pdf:
        if len(pdf.pages) > max_pages:
            raise ValueError("Alternate PDF text page budget exceeded; narrow the scope")
        wanted = range(1, len(pdf.pages) + 1) if numbers is None else sorted(set(numbers))
        if any(n < 1 or n > len(pdf.pages) for n in wanted):
            raise ValueError("Invalid alternate PDF text page number")
        return [(n, pdf.pages[n - 1].extract_text() or "") for n in wanted]


def search_pdf_text(catalog, query, *, scope, allowed_versions=None, page_policy=None):
    profile = settings(catalog.root)
    audit = {"profile_id": profile["profile_id"], "profile_sha256": file_sha(catalog.root / PROFILE),
             "extractor": profile["extractor"], "pdfplumber_version": pdfplumber.__version__,
             "max_reparsed_pages": profile["max_reparsed_pages"], "reparsed_pages": 0,
             "documents": [], "ocr_performed": False}
    if scope is None:
        raise ValueError("Alternate PDF text retrieval requires an explicit document scope")
    if topic_for(query, load_profile(catalog.root)) is None:
        return Corpus(snapshot=catalog.snapshot), [], {"stop_reason": "unsupported_alternate_text_topic",
                                                      "alternate_text_layer": audit}
    if allowed_versions is None or allowed_versions:
        where, params = scope.sql()
        with catalog.connect() as db:
            eligible_counts = [(version, count) for version, count in db.execute(
                "SELECT version_id,pages FROM documents d WHERE " + where +
                " AND json_extract(d.metadata_json,'$.media_type')='application/pdf'", params)
                if allowed_versions is None or version in allowed_versions]
        expected_pages = sum(count for _, count in eligible_counts)
        if expected_pages > profile["max_reparsed_pages"]:
            raise ValueError(f"Alternate PDF text metadata page budget exceeded: {expected_pages} > "
                             f"{profile['max_reparsed_pages']}; narrow the scope")

    def loader(catalog, version_id):
        # search_financial intersects issuer/period and the gateway allowlist before this call.
        version, _, _ = catalog.page(version_id, 1)
        payload = catalog.store.read_blob(version.content_hash)
        texts = extract_text_pages(payload, version.content_hash,
                                   max_pages=profile["max_reparsed_pages"] - audit["reparsed_pages"])
        audit["reparsed_pages"] += len(texts)
        audit["documents"].append({"version_id": version_id, "content_hash": version.content_hash,
                                   "pages": len(texts), "text_pages": sum(bool(t.strip()) for _, t in texts),
                                   "no_text_pages": sum(not t.strip() for _, t in texts)})
        return [EvidencePage(record_id=version.record_id, version_id=version_id, ticker=version.ticker,
                             related_tickers=version.related_tickers, content_hash=version.content_hash,
                             page=n, text=text, text_hash=sha256(text.encode()), source_url=version.source_url,
                             retrieved_at=version.retrieved_at, extractor=profile["extractor"],
                             extraction_status="text_present" if text.strip() else "no_text_ocr_not_performed",
                             data_kind=version.data_kind) for n, text in texts]

    data, hits, trace = search_financial(catalog, query, scope=scope, allowed_versions=allowed_versions,
                                        page_loader=loader, page_policy=page_policy)
    trace["alternate_text_layer"] = audit
    return data, hits, trace


def search_annual_pdf_text(catalog, query, *, scope, allowed_versions=None):
    policy = load_policy(catalog.root)
    data, hits, trace = search_pdf_text(catalog, query, scope=scope, allowed_versions=allowed_versions,
                                       page_policy=gate(catalog.root))
    trace["annual_page_policy"] = {"policy_id": policy["policy_id"],
                                   "policy_sha256": file_sha(catalog.root / PAGE_POLICY)}
    return data, hits, trace


def replay_selected_text(root, pages, store):
    """Recheck selected derived spans from raw PDF; no dependence on a mutable text cache."""
    profile = settings(root)
    keys, groups = set(), {}
    for item in pages:
        page = EvidencePage.model_validate(item)
        key = (page.version_id, page.page)
        if key in keys or page.extractor != profile["extractor"] or sha256(page.text.encode()) != page.text_hash:
            raise ValueError("Alternate PDF selected text identity/hash mismatch")
        keys.add(key)
        groups.setdefault(page.content_hash, []).append(page)
    if len(keys) > 3:
        raise ValueError("Alternate selected PDF text exceeds table page budget")
    for digest, selected in groups.items():
        raw = store.read_blob(digest)
        extracted = dict(extract_text_pages(raw, digest, max_pages=profile["max_reparsed_pages"],
                                            numbers=[p.page for p in selected]))
        if any(p.text != extracted[p.page] for p in selected):
            raise ValueError("Alternate selected text differs from raw PDF extraction")
