"""Bounded public news ingestion; observed publication metadata is not historical proof."""

import argparse
import copy
import gzip
import hashlib
import io
import json
import re
import time
import unicodedata
import urllib.robotparser
import xml.etree.ElementTree as ET
from collections import Counter
from datetime import UTC, date, datetime
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit

from bs4 import BeautifulSoup

from pit_haf.data.evidence import EvidencePage, EvidenceVersion, version_id_for
from pit_haf.data.pilot import USER_AGENT, fetch_public, publish_summary
from pit_haf.data.snapshots import SnapshotStore

EXTRACTOR = "html-article/2;beautifulsoup4;visible-blocks;no_ocr"
MAX_HTML = 3 * 1024 * 1024


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def decode_html(raw: bytes) -> str:
    if raw.startswith(b"\x1f\x8b"):
        with gzip.GzipFile(fileobj=io.BytesIO(raw)) as stream:
            raw = stream.read(MAX_HTML + 1)
    if len(raw) > MAX_HTML:
        raise ValueError("Decoded HTML/feed exceeds bounded size")
    text = raw.decode("utf-8-sig")
    if "\x00" in text:
        raise ValueError("Response is not UTF-8 HTML/XML")
    return text


def normalize_url(url: str, base: str, hosts: set[str]) -> str:
    value = urlsplit(urljoin(base, url))
    if (value.scheme not in {"https", "http"} or value.hostname not in hosts or
            value.username or value.password or value.port not in (None, 80, 443)):
        raise ValueError("News locator outside source allowlist")
    query = [(k, v) for k, v in parse_qsl(value.query, keep_blank_values=True)
             if not k.lower().startswith("utm_") and k.lower() not in {"fbclid", "gclid"}]
    return urlunsplit(("https", value.hostname, value.path, urlencode(query), ""))


def normalized(value: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", value.lower().replace("đ", "d"))
                   if not unicodedata.combining(c))


def link_tickers(title: str, lede: str, aliases: dict) -> tuple[str, ...]:
    text = title + " " + lede
    folded = normalized(text)
    found = []
    for ticker, names in aliases.items():
        if re.search(rf"\b{re.escape(ticker)}\b", text) or any(
            re.search(rf"(?<!\w){re.escape(normalized(name))}(?!\w)", folded) for name in names
        ):
            found.append(ticker)
    return tuple(sorted(found))


def publication_fields(observations: list[dict]) -> dict:
    """Date-only/naive strings stay date-only; never manufacture an available_at."""
    for item in observations:
        raw = str(item.get("value") or "").strip()
        if not raw:
            continue
        try:
            if re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw):
                return {"publication_date": date.fromisoformat(raw).isoformat(),
                        "timestamp_precision": "day"}
            value = (datetime.fromisoformat(raw.replace("Z", "+00:00"))
                     if re.match(r"\d{4}-\d{2}-\d{2}T", raw) else parsedate_to_datetime(raw))
            if value.tzinfo is None or value.utcoffset() is None:
                return {"publication_date": value.date().isoformat(), "timestamp_precision": "day"}
            return {"published_at": value.astimezone(UTC).isoformat(),
                    "publication_date": value.date().isoformat(), "timestamp_precision": "second"}
        except (TypeError, ValueError, OverflowError):
            continue
    return {}


def parse_article(raw: bytes, source: dict, candidate: dict) -> dict:
    soup = BeautifulSoup(decode_html(raw), "html.parser")
    observations, author = [], None
    for meta in soup.select("meta[content]"):
        key = (meta.get("property") or meta.get("name") or meta.get("itemprop") or "").lower()
        value = meta["content"].strip()
        if key in {"article:published_time", "pubdate", "datepublished", "publication_date"}:
            observations.append({"origin": "html_meta:" + key, "value": value})
        if key == "author" and value:
            author = value[:300]
    for script in soup.select('script[type="application/ld+json"]'):
        try:
            payload = json.loads(script.string or script.get_text())
            stack = payload if isinstance(payload, list) else [payload]
            while stack:
                item = stack.pop()
                if not isinstance(item, dict):
                    continue
                if item.get("isAccessibleForFree") in (False, "false", "False"):
                    raise ValueError("Paywalled article metadata; no hidden-body extraction")
                if item.get("datePublished"):
                    observations.append({"origin": "jsonld:datePublished", "value": item["datePublished"]})
                for child in item.values():
                    if isinstance(child, dict):
                        stack.append(child)
                    elif isinstance(child, list):
                        stack.extend(child)
        except (json.JSONDecodeError, TypeError):
            continue
    if candidate.get("feed_published"):
        observations.append({"origin": "rss:pubDate", "value": candidate["feed_published"]})
    if source.get("publication_selector"):
        node = soup.select_one(source["publication_selector"])
        if node:
            visible_date = node.get_text(" ", strip=True)
            match = re.search(r"(\d{1,2})/(\d{1,2})/(\d{4})", visible_date)
            if match:
                try:
                    value = date(int(match[3]), int(match[2]), int(match[1])).isoformat()
                    observations.insert(0, {"origin": "visible_date_no_timezone",
                                            "value": value, "source_text": visible_date})
                except ValueError:
                    pass
    title_node = soup.select_one(source.get("title_selector", "h1"))
    title = title_node.get_text(" ", strip=True) if title_node else ""
    if len(title) < 10:
        raise ValueError("Article title missing; listing/error pages must not become articles")
    root = next((node for selector in source["body_selectors"]
                 if (node := soup.select_one(selector)) is not None), None)
    if root is None:
        raise ValueError("Reviewed article-body selector not found")
    if (root.get("hidden") is not None or root.get("aria-hidden") == "true" or
            re.search(r"display\s*:\s*none|visibility\s*:\s*hidden", root.get("style", ""), re.I)):
        raise ValueError("Article body is hidden; no bypass")
    for node in list(root.select(
        "script,style,nav,aside,form,button,iframe,[hidden],[aria-hidden='true'],"
        ".related-news,.content-relate,.VCSortableInPreviewMode[type='RelatedOneNews'],"
        ".ads,.advertisement,.subscription,.paywall"
    )):
        node.decompose()
    for selector in source.get("remove_selectors", []):
        for node in list(root.select(selector)):
            node.decompose()
    for node in list(root.select("[style]")):
        if node.attrs and re.search(r"display\s*:\s*none|visibility\s*:\s*hidden", node.get("style", ""), re.I):
            node.decompose()
    paragraphs = []
    for node in root.select("p,h2,h3,li"):
        if any(parent.name in {"p", "h2", "h3", "li"} for parent in node.parents
               if parent is not root):
            continue
        if "display:none" in node.get("style", "").replace(" ", ""):
            continue
        text = " ".join(node.get_text(" ", strip=True).split())
        if text:
            paragraphs.append(text)
    body = "\n\n".join(paragraphs)
    if len(body) < source.get("min_body_chars", 400) or len(body) > 250_000:
        raise ValueError("Article body too short/large; no summary-only indexing")
    lede_node = soup.select_one(source.get("lede_selector", ".description"))
    lede = " ".join(lede_node.get_text(" ", strip=True).split()) if lede_node else ""
    text = title + "\n\n" + (lede + "\n\n" if lede and lede not in paragraphs else "") + body
    return {"title": title.strip(), "lede": lede[:2500], "text": text,
            "body_sha256": sha(body.encode()), "author": author,
            "publication_observations": observations, **publication_fields(observations)}


def fetch_policies(config: dict, store: SnapshotStore, delay: float) -> tuple[dict, list]:
    policies, events = {}, []
    for host in sorted({h for source in config["sources"] for h in source["allowed_hosts"]}):
        url = f"https://{host}/robots.txt"
        event = {"kind": "news_robots", "source_url": url}
        try:
            raw, meta = fetch_public(url, {host}, timeout=15, max_bytes=1024 * 1024)
            robot = urllib.robotparser.RobotFileParser(url)
            robot.parse(decode_html(raw).splitlines())
            policies[host] = robot
            event.update(status="downloaded", content_hash=store.put_blob(raw),
                         retrieved_at=meta["retrieved_at"], http_status=meta["http_status"])
        except Exception as exc:
            event.update(status="policy_unknown", error_type=type(exc).__name__, error=str(exc))
        store.log_acquisition(event)
        events.append(event)
        time.sleep(delay)
    return policies, events


def check_policy(url: str, policies: dict) -> None:
    policy = policies.get(urlsplit(url).hostname)
    if policy is not None and not policy.can_fetch(USER_AGENT, url):
        raise ValueError("robots.txt disallows configured URL")


def discover(config: dict, *, store: SnapshotStore, output: Path, delay: float = 1) -> dict:
    output.mkdir(parents=True, exist_ok=False)
    policies, resources = fetch_policies(config, store, delay)
    candidates, duplicates = {}, []
    maximum = min(config.get("max_candidates", 800), 1500)
    for source in config["sources"]:
        hosts = set(source["allowed_hosts"])
        queue = [(url, "feed") for url in source.get("feeds", [])]
        queue += [(url, "listing") for url in source.get("listings", [])]
        visited, source_count, listing_count = set(), 0, 0
        while queue and source_count < source.get("max_candidates", 150) and len(candidates) < maximum:
            url, kind = queue.pop(0)
            if kind == "listing" and listing_count >= source.get("max_listing_pages", 1):
                continue
            if url in visited:
                continue
            visited.add(url)
            entry = {"kind": "news_discovery_" + kind, "source_id": source["source_id"], "url": url}
            try:
                check_policy(url, policies)
                raw, meta = fetch_public(url, hosts, timeout=20, max_bytes=MAX_HTML)
                digest = store.put_blob(raw)
                entry.update(status="downloaded", content_hash=digest, retrieved_at=meta["retrieved_at"])
                text = decode_html(raw)
                items = []
                if kind == "feed":
                    if "<!DOCTYPE" in text.upper() or "<!ENTITY" in text.upper():
                        raise ValueError("Feed DTD/entities are not accepted")
                    root = ET.fromstring(text.lstrip())
                    feed_items = root.findall(".//item")
                    if not feed_items:
                        raise ValueError("RSS returned no article entries; not an article dataset")
                    for item in feed_items[:source.get("max_per_feed", 60)]:
                        items.append({"url": item.findtext("link", ""),
                                      "feed_title": item.findtext("title", ""),
                                      "feed_published": item.findtext("pubDate", "")})
                else:
                    listing_count += 1
                    soup = BeautifulSoup(text, "html.parser")
                    items = [{"url": a["href"], "feed_title": a.get_text(" ", strip=True)}
                             for a in soup.select(source.get("link_selector", "a[href]"))
                             if a.get("href")]
                    if listing_count < source.get("max_listing_pages", 1):
                        for a in soup.select(source.get("pagination_selector", ".pagination a[href]")):
                            if a.get("href"):
                                next_url = normalize_url(a["href"], url, hosts)
                                scoped = (urlsplit(next_url).path == urlsplit(url).path or
                                          (source.get("listing_path_prefix") and
                                           urlsplit(next_url).path.startswith(source["listing_path_prefix"])))
                                if scoped and next_url not in visited:
                                    queue.append((next_url, "listing"))
                for item in items:
                    try:
                        locator = normalize_url(item["url"], url, hosts)
                    except ValueError:
                        continue
                    if not re.search(source["article_pattern"], locator):
                        continue
                    if locator in candidates:
                        duplicates.append({"url": locator, "listing_url": url})
                        continue
                    record = "NEWS-" + source["source_id"] + "-" + sha(locator.encode())[:20]
                    candidates[locator] = {**item, "url": locator, "record_id": record,
                                           "source_id": source["source_id"], "listing_url": url,
                                           "listing_snapshot_hash": digest}
                    source_count += 1
                    if source_count >= source.get("max_candidates", 150) or len(candidates) >= maximum:
                        break
            except Exception as exc:
                entry.update(status="failed", error_type=type(exc).__name__, error=str(exc))
            resources.append(entry)
            store.log_acquisition(entry)
            print(json.dumps({"source": source["source_id"], "resource": kind,
                              "status": entry["status"], "candidates": source_count}), flush=True)
            time.sleep(delay)
    result = {"config": config, "created_at": datetime.now(UTC).isoformat(), "resources": resources,
              "candidates": list(candidates.values()), "duplicate_discovery_links": duplicates,
              "research_prediction_results": False}
    (output / "discovery.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


def acquire(discovery: dict, *, store: SnapshotStore, output: Path,
            skip_registered: bool = False, delay: float = 1) -> dict:
    output.mkdir(parents=True, exist_ok=False)
    config = discovery["config"]
    sources = {s["source_id"]: s for s in config["sources"]}
    policies, resources = fetch_policies(config, store, delay)
    registered = {}
    for version in store.versions():
        registered.setdefault(version.record_id, []).append(version)
    events, specs, blocked = [], [], {}
    pages_path = output / "pages.jsonl"
    with pages_path.open("x", encoding="utf-8", newline="\n") as stream:
        for candidate in discovery["candidates"]:
            source = sources[candidate["source_id"]]
            event = {"record_id": candidate["record_id"], "source_id": source["source_id"],
                     "source_url": candidate["url"], "status": "failed", "ticker": "MARKET"}
            spec = {"record_id": candidate["record_id"], "source_id": source["source_id"],
                    "source_url": candidate["url"], "listing_url": candidate["listing_url"],
                    "ticker": "MARKET", "title": (candidate.get("feed_title") or candidate["url"]).strip(),
                    "media_type": "text/html", "publisher": source["publisher"],
                    "document_type": source["document_type"], "evidence_scope": "market",
                    "statement_scope": "not_applicable",
                    "data_kind": config.get("data_kind", "real_document"),
                    "rights_note": "Publisher copyright; local research inspection only; no text/raw redistribution license."}
            try:
                if blocked.get(source["source_id"], 0) >= 3:
                    raise ValueError("Source circuit open after consecutive acquisition denials; no bypass")
                check_policy(candidate["url"], policies)
                prior = registered.get(candidate["record_id"], []) if skip_registered else []
                if prior:
                    if len(prior) != 1:
                        raise ValueError("Local news reuse needs exactly one immutable version")
                    version = prior[0]
                    if version.source_url != candidate["url"] or version.media_type != "text/html":
                        raise ValueError("Reused news source identity mismatch")
                    raw = store.read_blob(version.content_hash)
                    meta = {"retrieved_at": version.retrieved_at.isoformat()}
                    event["registration"] = "local_reuse_without_remote_revalidation"
                else:
                    raw, meta = fetch_public(candidate["url"], set(source["allowed_hosts"]),
                                             timeout=20, max_bytes=MAX_HTML)
                raw_hash = store.put_blob(raw)
                event.update(content_hash=raw_hash, retrieved_at=meta["retrieved_at"])
                parsed = parse_article(raw, source, candidate)
                tickers = link_tickers(parsed["title"], parsed["lede"], config["ticker_aliases"])
                relevance_text = normalized(parsed["title"] + " " + parsed["lede"] + " " + parsed["text"][:1500])
                if (not tickers and not source.get("issuer_ticker") and config.get("topic_terms") and
                        not any(re.search(rf"(?<!\w){re.escape(normalized(term))}(?!\w)", relevance_text)
                                for term in config["topic_terms"])):
                    raise ValueError("Outside declared financial/industry relevance; metadata retained")
                if source.get("issuer_ticker") and source["issuer_ticker"] not in tickers:
                    tickers = tuple(sorted((*tickers, source["issuer_ticker"])))
                spec.update(title=parsed["title"], author=parsed["author"], related_tickers=list(tickers),
                            ticker=tickers[0] if tickers else "MARKET",
                            evidence_scope="issuer" if tickers else "market",
                            entity_linking_basis="title_and_lede_alias_match_or_issuer_source;not_human_gold")
                spec.update({key: parsed[key] for key in ("published_at", "publication_date", "timestamp_precision")
                             if key in parsed})
                spec["reporting_period"] = parsed.get("publication_date", "")[:4] or None
                if prior:
                    # Preserve first-observed metadata, including linking decisions.
                    spec = {key: value for key, value in version.model_dump(mode="json").items()
                            if key in spec}
                else:
                    version = EvidenceVersion(**spec, version_id=version_id_for(spec["record_id"], raw_hash),
                                              content_hash=raw_hash, retrieved_at=meta["retrieved_at"],
                                              system_recorded_at=datetime.now(UTC),
                                              listing_snapshot_hash=candidate["listing_snapshot_hash"])
                    store.register(version)
                canonical_metadata = version.model_dump(mode="json")
                spec = {key: canonical_metadata[key] for key in spec}
                page = EvidencePage(record_id=version.record_id, version_id=version.version_id,
                                    ticker=version.ticker, related_tickers=version.related_tickers,
                                    content_hash=raw_hash, page=1, text=parsed["text"],
                                    text_hash=sha(parsed["text"].encode()), source_url=version.source_url,
                                    retrieved_at=version.retrieved_at, extractor=EXTRACTOR,
                                    extraction_status="text_present", data_kind=version.data_kind)
                stream.write(page.model_dump_json() + "\n")
                event.update(status="extracted", version_id=version.version_id, ticker=version.ticker,
                             pages=1, text_pages=1, empty_pages=0, media_type="text/html",
                             body_sha256=parsed["body_sha256"],
                             publication_observations=parsed["publication_observations"],
                             historical_eligibility="quarantined_no_reviewed_time_or_revision_proof")
                blocked[source["source_id"]] = 0
            except Exception as exc:
                event.update(error_type=type(exc).__name__, error=str(exc))
                if any(value in str(exc) for value in ("HTTP 403", "HTTP 429", "CERTIFICATE_VERIFY_FAILED")):
                    blocked[source["source_id"]] = blocked.get(source["source_id"], 0) + 1
            specs.append(spec)
            events.append(event)
            store.log_acquisition(event)
            print(json.dumps({key: event.get(key) for key in ("record_id", "status", "ticker", "error")}), flush=True)
            time.sleep(delay)
    manifest = {"release_id": config["release_id"], "allowed_hosts": sorted({
        h for s in sources.values() for h in s["allowed_hosts"]}),
        "sources": [{"source_id": c["source_id"], "listing_url": c["listing_url"]}
                    for c in discovery["candidates"]],
        "documents": specs, "target_documents": len(specs)}
    canonical = json.dumps(manifest, ensure_ascii=False, sort_keys=True).encode()
    (output / "sources.json").write_bytes(canonical)
    successful = [e for e in events if e["status"] == "extracted"]
    summary = {"run_kind": ("real_public_news_acquisition_and_current_text_qa"
                             if config.get("data_kind", "real_document") == "real_document" else "test_fixture"),
               "created_at": datetime.now(UTC).isoformat(), "research_prediction_results": False,
               "historical_availability_inferred": False, "manifest_hash": sha(canonical),
               "configured_documents": len(specs), "target_documents": len(specs),
               "success_documents": len(successful), "failed_documents": len(specs) - len(successful),
               "target_shortfall": len(specs) - len(successful), "page_count": len(successful),
               "text_page_count": len(successful), "empty_page_count_no_ocr": 0,
               "strict_gateway_deliveries": 0, "strict_eligibility_note": "All news observation-only; no reviewed historical proof.",
               "pages_sha256": sha(pages_path.read_bytes()), "pages_file": str(pages_path.resolve()),
               "success_by_ticker": dict(Counter(e["ticker"] for e in successful)),
               "resources": resources, "documents": events,
               "limitations": ["HTML article section 1 is not a physical PDF page.",
                               "Publication strings and ticker links are source observations, not reviewed ground truth.",
                               "News text/raw HTML stays local; no redistribution rights established."]}
    publish_summary(output, summary)
    return summary


def reextract(summary_path: Path, discovery_path: Path, *, store: SnapshotStore, output: Path) -> dict:
    """Review current local bytes with the current extractor; preserve all first observations.

    No HTTP requests, metadata rewrites or failed-source retries. Old extraction files remain intact.
    """
    raw_summary = summary_path.read_bytes()
    result = copy.deepcopy(json.loads(raw_summary))
    raw_pages = (summary_path.parent / "pages.jsonl").read_bytes()
    if sha(raw_pages) != result["pages_sha256"]:
        raise ValueError("Original news page snapshot checksum mismatch")
    discovery = json.loads(discovery_path.read_bytes())
    candidates = {c["record_id"]: c for c in discovery["candidates"]}
    sources = {s["source_id"]: s for s in discovery["config"]["sources"]}
    versions = {v.version_id: v for v in store.versions()}
    pages, changes = [], []
    original_text = {}
    for line in raw_pages.splitlines():
        if line.strip():
            page = EvidencePage.model_validate_json(line)
            if sha(page.text.encode()) != page.text_hash:
                raise ValueError("Original news page text checksum mismatch")
            original_text[page.version_id] = page.text_hash
    for row in result["documents"]:
        if row["status"] != "extracted":
            continue
        version = versions[row["version_id"]]
        candidate = candidates[row["record_id"]]
        if (version.media_type != "text/html" or version.source_url != candidate["url"] or
                version.content_hash != row["content_hash"]):
            raise ValueError("Original news and registry identity disagree")
        try:
            parsed = parse_article(store.read_blob(version.content_hash), sources[candidate["source_id"]], candidate)
            if parsed["title"] != version.title:
                raise ValueError("Headline differs from first-observed immutable metadata; review needed")
            page = EvidencePage(
                record_id=version.record_id, version_id=version.version_id, ticker=version.ticker,
                related_tickers=version.related_tickers, content_hash=version.content_hash,
                page=1, text=parsed["text"], text_hash=sha(parsed["text"].encode()),
                source_url=version.source_url, retrieved_at=version.retrieved_at,
                extractor=EXTRACTOR, extraction_status="text_present", data_kind=version.data_kind)
            pages.append(page.model_dump_json())
            row["body_sha256"] = parsed["body_sha256"]
            if original_text[version.version_id] != page.text_hash:
                changes.append({"version_id": version.version_id, "old_text_hash": original_text[version.version_id],
                                "new_text_hash": page.text_hash})
        except ValueError as exc:
            row.update(status="failed", error_type="offline_article_review", error=str(exc))
    output.mkdir(parents=True, exist_ok=False)
    raw_manifest = (summary_path.parent / "sources.json").read_bytes()
    manifest = json.loads(raw_manifest)
    if sha(raw_manifest) != result["manifest_hash"]:
        raise ValueError("Original news source manifest checksum mismatch")
    by_record = {row["record_id"]: row for row in result["documents"]}
    for spec in manifest["documents"]:
        row = by_record[spec["record_id"]]
        if row.get("version_id"):
            canonical_metadata = versions[row["version_id"]].model_dump(mode="json")
            for key in spec:
                spec[key] = canonical_metadata[key]
    canonical_manifest = json.dumps(manifest, ensure_ascii=False, sort_keys=True).encode()
    (output / "sources.json").write_bytes(canonical_manifest)
    payload = ("\n".join(pages) + ("\n" if pages else "")).encode()
    (output / "pages.jsonl").write_bytes(payload)
    successful = [r for r in result["documents"] if r["status"] == "extracted"]
    result.update(
        run_kind="test_fixture" if result["run_kind"] == "test_fixture" else "offline_news_extraction_review",
        created_at=datetime.now(UTC).isoformat(), network_requests=0,
        source_summary_sha256=sha(raw_summary), source_pages_sha256=sha(raw_pages),
        source_manifest_sha256=sha(raw_manifest), manifest_hash=sha(canonical_manifest),
        source_discovery_sha256=sha(discovery_path.read_bytes()), extractor=EXTRACTOR,
        extraction_text_changes=changes, success_documents=len(successful),
        failed_documents=len(result["documents"]) - len(successful),
        target_shortfall=max(0, result["target_documents"] - len(successful)),
        page_count=len(pages), text_page_count=len(pages), pages_sha256=sha(payload),
        pages_file=str((output / "pages.jsonl").resolve()),
        success_by_ticker=dict(Counter(r["ticker"] for r in successful)))
    publish_summary(output, result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["discover", "acquire", "reextract"])
    parser.add_argument("--config", type=Path)
    parser.add_argument("--discovery", type=Path)
    parser.add_argument("--summary", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--root", type=Path, default=Path("data/cache/evidence"))
    parser.add_argument("--skip-registered", action="store_true")
    args = parser.parse_args()
    store = SnapshotStore(args.root)
    if args.action == "discover":
        if not args.config:
            parser.error("discover requires --config")
        result = discover(json.loads(args.config.read_text(encoding="utf-8")), store=store, output=args.output)
        print(json.dumps({"candidates": len(result["candidates"])}))
    elif args.action == "acquire":
        if not args.discovery:
            parser.error("acquire requires --discovery")
        result = acquire(json.loads(args.discovery.read_text(encoding="utf-8")), store=store,
                         output=args.output, skip_registered=args.skip_registered)
        print(json.dumps({k: result[k] for k in ("success_documents", "failed_documents")}))
    else:
        if not args.discovery or not args.summary:
            parser.error("reextract requires --discovery and --summary")
        result = reextract(args.summary, args.discovery, store=store, output=args.output)
        print(json.dumps({k: result[k] for k in ("success_documents", "failed_documents")}))


if __name__ == "__main__":
    main()
