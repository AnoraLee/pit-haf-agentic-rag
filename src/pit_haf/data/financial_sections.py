"""Bounded section-first PDF retrieval; literal spans and the legacy verifier stay intact."""

import json
import math
import re
from collections import Counter, defaultdict
from dataclasses import replace

from pit_haf.data.evidence import EvidencePage
from pit_haf.data.hub import file_sha
from pit_haf.llm.ollama import sha256
from pit_haf.ui.workspace import Corpus, Passage, tokens

PROFILE = "configs/financial_sections_v0_3.json"


def normalized(text):
    return " ".join(tokens(text))


def contains(text, phrase):
    return " " + normalized(phrase) + " " in " " + text + " "


def load_profile(root):
    profile = json.loads((root / PROFILE).read_text(encoding="utf-8"))
    if (profile["profile_id"] != "financial_sections_v0.3" or profile["status"] != "development_not_frozen" or
            (profile["max_passages"], profile["max_passage_characters"], profile["max_context_characters"]) != (3, 700, 2100) or
            not 1 <= profile["max_pages"] <= 4000 or not 0 < profile["boilerplate_fraction"] <= 1):
        raise ValueError("Invalid financial retrieval development profile/budget")
    return profile


def topic_for(query, profile):
    text = normalized(query)
    return next((name for name, topic in profile["topics"].items()
                 if any(contains(text, phrase) for phrase in topic["query"])), None)


def lines(text):
    offset = 0
    for line in text.splitlines(keepends=True):
        yield offset, offset + len(line), normalized(line)
        offset += len(line)


def header_years(text):
    """Observed column-header years, not proof of period semantics or availability."""
    rows = text.splitlines()
    years = set()
    for i, line in enumerate(rows):
        found = re.findall(r"(?<!\d)(?:19|20)\d{2}(?!\d)", line)
        if not found or len(tokens(line)) > 18:
            continue
        folded = normalized(line)
        shape = (bool(re.fullmatch(r"\s*(?:31/12/)?(?:19|20)\d{2}\s*", line)) or
                 any(contains(folded, x) for x in ("chỉ tiêu", "thuyết minh", "mã số", "stt")) or
                 any(contains(folded, x) for x in ("vnd", "vnđ", "đồng", "triệu")))
        if not shape:
            continue
        nearby = normalized(" ".join(rows[max(0, i - 1):i + 3]))
        if any(contains(nearby, unit) for unit in ("vnd", "vnđ", "đồng", "triệu")):
            years.update(found)
    return years


def score_text(text, topic):
    return (8 * sum(contains(text, x) for x in topic["anchors"]) +
            24 * sum(contains(text, x) for x in topic["headings"]) -
            14 * sum(contains(text, x) for x in topic["penalties"]))


def partition(text, size=700):
    """Partition without rewriting text or splitting numeric strings where avoidable."""
    start = 0
    while start < len(text):
        end = min(start + size, len(text))
        if end < len(text):
            boundary = text.rfind("\n", start + size // 2, end)
            if boundary < 0:
                boundary = text.rfind(" ", start + size // 2, end)
            if boundary >= 0:
                end = boundary + 1
        yield start, end
        start = end


def windows(page, topic, boilerplate):
    text = page.text
    whole = list(partition(text))
    if len(whole) <= 3:
        return [(start, end, "complete_page") for start, end in whole]
    candidates = {}
    for start, _, line in lines(text):
        if not line or line in boilerplate:
            continue
        target = any(contains(line, p) for p in topic["anchors"] + topic["headings"])
        qualifier = bool(re.search(r"\b(?:19|20)\d{2}\b", line)) or any(
            contains(line, p) for p in ("đơn vị", "triệu vnd", "tỷ đồng", "tỷ vnđ"))
        if not target and not qualifier:
            continue
        left = text.rfind("\n", max(0, start - 90), start)
        left = left + 1 if left >= 0 else max(0, start - 90)
        end = next(partition(text[left:]))[1] + left
        value = score_text(normalized(text[left:end]), topic)
        role = "target" if target else "header_candidate"
        candidates[(left, end)] = (value + (3 if qualifier else 0), role)
    ranked = sorted(candidates, key=lambda key: (-candidates[key][0], key))
    return [(*key, candidates[key][1]) for key in ranked]


def search_financial(catalog, query, *, scope, allowed_versions=None, page_loader=None, page_policy=None):
    """Filter metadata/allowlist before loading text or computing per-document repeats.

    Returns a bounded source preview plus an evaluator-only ranking trace. It never
    loads audit answers, gold locators, case IDs or issuer-specific page mappings.
    """
    if scope is None:
        raise ValueError("Financial section retrieval requires an explicit document scope")
    profile = load_profile(catalog.root)
    topic_name = topic_for(query, profile)
    trace = {"profile_id": profile["profile_id"], "profile_sha256": file_sha(catalog.root / PROFILE),
             "topic": topic_name, "pages_scored": 0, "historical_statistics": allowed_versions is not None,
             "metadata_scope": scope.model_dump(), "ranked_pages": [], "selected_windows": [],
             "semantic_support": "not_assessed"}
    if allowed_versions is not None and not allowed_versions:
        trace["stop_reason"] = "empty_gateway_allowlist"
        return Corpus(snapshot=catalog.snapshot), [], trace
    if topic_name is None:
        trace["fallback_reason"] = "no_financial_topic_detected; same scoped lexical search"
        data, hits = catalog.search(query, ticker=scope.ticker, scope=scope, allowed_versions=allowed_versions)
        return data, hits, trace
    where, params = scope.sql()
    with catalog.connect() as db:
        eligible = [r[0] for r in db.execute("SELECT version_id FROM documents d WHERE " + where +
                    " AND json_extract(d.metadata_json,'$.media_type')='application/pdf' ORDER BY version_id", params)
                    if allowed_versions is None or r[0] in allowed_versions]
        rows = []
        for version_id in eligible:
            loaded = (page_loader(catalog, version_id) if page_loader else
                      (EvidencePage.model_validate_json(row[0]) for row in db.execute(
                          "SELECT page_json FROM pages WHERE version_id=? ORDER BY page", (version_id,))))
            for page in loaded:
                if len(rows) >= profile["max_pages"]:
                    raise ValueError("Too many eligible PDF pages; narrow the report period/scope")
                if page.version_id != version_id or sha256(page.text.encode()) != page.text_hash:
                    raise ValueError("Financial retrieval page identity/hash mismatch")
                rows.append(page)
    frequencies, page_counts = defaultdict(Counter), Counter(p.version_id for p in rows)
    for page in rows:
        frequencies[page.version_id].update({line for _, _, line in lines(page.text) if len(line) >= 4})
    repeated = {version: {line for line, count in counts.items()
                         if count >= max(3, math.ceil(page_counts[version] * profile["boilerplate_fraction"]))}
                for version, counts in frequencies.items()}
    topic = profile["topics"][topic_name]
    ranked = []
    expected_year = (scope.reporting_period or "")[:4]
    numeric_topics = {"income", "revenue", "assets", "cash"}
    observations = {}
    if page_policy:
        trace["page_year_checks"] = []
    for page in rows:
        clean = " ".join(line for _, _, line in lines(page.text) if line not in repeated[page.version_id])
        score = score_text(clean, topic)
        observed_years = header_years(page.text)
        if page_policy:
            check = page_policy(page, expected_year, topic_name)
            observations[(page.version_id, page.page)] = check
            trace["page_year_checks"].append({"version_id": page.version_id, "page": page.page, **check})
            if not check["eligible"]:
                continue
            observed_years = set(check["years"])
        if topic_name in numeric_topics and observed_years and expected_year and expected_year not in observed_years:
            continue
        if score <= 0:
            continue
        if contains(clean, "mục lục") or re.search(r"\.{5,}", page.text):
            score -= 20
        score += min(3, len(set(tokens(query)) & set(clean.split())))
        ranked.append((score, page))
    ranked.sort(key=lambda item: (-item[0], item[1].version_id, item[1].page))
    trace["pages_scored"] = len(rows)
    trace["ranked_pages"] = [{"version_id": p.version_id, "page": p.page, "score": s,
                              "observed_header_years": (observations[(p.version_id, p.page)]["years"] if page_policy else
                                                        sorted(header_years(p.text)))} for s, p in ranked[:12]]
    candidates = []
    wanted_years = set(re.findall(r"\b(?:19|20)\d{2}\b", query)) | ({expected_year} if expected_year else set())
    for score, page in ranked[:8]:
        if score <= 0 or score < .4 * ranked[0][0]:
            continue
        summary_page = (topic_name in numeric_topics and len(list(partition(page.text))) <= 3 and
                        any(contains(normalized(page.text), x) for x in (
                            "tóm tắt các chỉ số tài chính", "tình hình tài chính và kết quả kinh doanh nổi bật")))
        for start, end, role in windows(page, topic, repeated[page.version_id]):
            content = normalized(page.text[start:end])
            anchors = {p for p in topic["anchors"] if contains(content, p)}
            qualifiers = {p for p in ("đơn vị", "triệu vnd", "tỷ đồng", "tỷ vnđ", "vnd") if contains(content, p)}
            qualifiers.update(set(re.findall(r"\b(?:19|20)\d{2}\b", content)) & wanted_years)
            candidates.append((score, page, start, end, role, anchors, qualifiers, summary_page))
    hits, covered, qualifications = [], set(), set()
    while candidates and len(hits) < profile["max_passages"]:
        def marginal(candidate):
            score, page, start, end, _, anchors, qualifiers, summary_page = candidate
            overlap = max((max(0, min(end, h.end) - max(start, h.start)) / (end - start)
                           for h in hits if h.version_id == page.version_id and h.page == page.page), default=0)
            subtotal = topic_name == "cash" and contains(normalized(page.text[start:end]), "trước những thay đổi")
            return (20 * len(anchors - covered) + 4 * len(qualifiers - qualifications) + score / 2 +
                    40 * summary_page -
                    50 * overlap - 16 * subtotal)
        candidate = max(candidates, key=marginal)
        candidates.remove(candidate)
        score, page, start, end, role, anchors, qualifiers, _ = candidate
        if any(h.version_id == page.version_id and h.page == page.page and
               max(0, min(end, h.end) - max(start, h.start)) > .3 * min(end - start, h.end - h.start) for h in hits):
            continue
        hits.append(Passage(page.version_id, page.record_id, page.ticker, page.page, start, end,
                            page.text[start:end], page.text_hash, score))
        covered.update(anchors)
        qualifications.update(qualifiers)
        trace["selected_windows"].append({"version_id": page.version_id, "page": page.page,
                                          "start": start, "end": end, "role": role,
                                          "anchors": sorted(anchors), "qualifiers": sorted(qualifiers)})
    data = catalog.subset((p.version_id, p.page) for p in hits)
    if page_loader:
        selected_keys = {(h.version_id, h.page) for h in hits}
        data = replace(data, pages=tuple(p for p in rows if (p.version_id, p.page) in selected_keys))
    for hit in hits:
        page = next(p for p in data.pages if (p.version_id, p.page) == (hit.version_id, hit.page))
        if page.text_hash != hit.page_text_hash or page.text[hit.start:hit.end] != hit.text:
            raise ValueError("Financial retrieval selected span differs from verified source")
    if not hits:
        trace["stop_reason"] = "no_matching_financial_section"
    return data, hits, trace
