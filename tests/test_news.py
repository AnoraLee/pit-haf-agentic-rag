"""Synthetic HTML/RSS only; no network, real articles, gold or inference metrics."""

import gzip
import hashlib
import json
import urllib.robotparser

import pytest

from pit_haf.data import news
from pit_haf.data.evidence import EvidencePage
from pit_haf.data.gateway import deliver_as_of
from pit_haf.data.pilot import validate_manifest_identity
from pit_haf.data.snapshots import SnapshotStore

SOURCE = {
    "source_id": "fixture", "publisher": "Synthetic publisher",
    "allowed_hosts": ["fixture.example"], "body_selectors": ["article"],
    "document_type": "news_article", "article_pattern": r"/article/",
    "feeds": ["https://fixture.example/rss"], "lede_selector": ".lede",
}
BODY = "Nội dung giả lập để kiểm thử, doanh thu đạt 100 tỷ đồng. " * 12


def html(extra="", body=None):
    return (f'<html><head>{extra}</head><body><h1>FPT và Hòa Phát: dữ liệu giả lập</h1>'
            '<p class="lede">Chỉ là dữ liệu kiểm thử ngoại tuyến.</p>'
            f'<article><p>{BODY if body is None else body}</p></article></body></html>').encode()


@pytest.mark.parametrize("raw,expected", [
    ("2024-04-03", {"publication_date": "2024-04-03", "timestamp_precision": "day"}),
    ("2024-04-03T09:30:00", {"publication_date": "2024-04-03", "timestamp_precision": "day"}),
    ("2024-04-03T09:30:00+07:00", {"publication_date": "2024-04-03", "timestamp_precision": "second",
                                  "published_at": "2024-04-03T02:30:00+00:00"}),
    ("Wed, 03 Apr 2024 09:30:00 +0700", {"publication_date": "2024-04-03", "timestamp_precision": "second",
                                        "published_at": "2024-04-03T02:30:00+00:00"}),
    ("not a date", {}),
])
def test_observed_dates_never_manufacture_availability(raw, expected):
    assert news.publication_fields([{"value": raw}]) == expected
    assert "available_at" not in expected


def test_visible_body_only_and_no_related_ad_or_hidden_text():
    raw = html(body=BODY + '<span style="DISPLAY: none">HIDDEN INLINE</span></p>'
               '<aside><p>ADVERT</p></aside><div class="related-news"><p>RELATED</p></div>'
               '<p hidden>HIDDEN BLOCK</p><script>SECRET</script><p>Visible closing sentence.')
    parsed = news.parse_article(raw, SOURCE, {})
    assert BODY.strip() in parsed["text"]
    assert "Visible closing sentence." in parsed["text"]
    for value in ("HIDDEN INLINE", "ADVERT", "RELATED", "HIDDEN BLOCK", "SECRET"):
        assert value not in parsed["text"]


@pytest.mark.parametrize("raw,reason", [
    (html('<script type="application/ld+json">{"hasPart":{"isAccessibleForFree":false}}</script>'), "Paywalled"),
    (html(body="Only a short RSS summary."), "too short"),
    (html().replace(b"<h1>", b"<h4>").replace(b"</h1>", b"</h4>"), "title missing"),
    (html().replace(b"<article>", b'<article hidden>'), "hidden"),
])
def test_inaccessible_listing_and_summary_only_content_is_rejected(raw, reason):
    with pytest.raises(ValueError, match=reason):
        news.parse_article(raw, SOURCE, {})


def test_ticker_links_are_bounded_title_and_lede_metadata():
    aliases = {"FPT": ["Tập đoàn FPT"], "HPG": ["Hòa Phát"], "GAS": ["PV GAS"]}
    assert news.link_tickers("FPT và Hòa Phát", "", aliases) == ("FPT", "HPG")
    assert news.link_tickers("FPTsoftware gas gasoil", "", aliases) == ()


def test_url_allowlist_and_tracking_normalization():
    assert news.normalize_url("http://fixture.example/article/a?utm_source=rss&x=1#part", "", {"fixture.example"}) == (
        "https://fixture.example/article/a?x=1")
    for url in ("https://other.example/article/a", "file:///article/a", "https://u:p@fixture.example/article/a"):
        with pytest.raises(ValueError):
            news.normalize_url(url, "", {"fixture.example"})


def test_compressed_html_has_decoded_size_bound(monkeypatch):
    monkeypatch.setattr(news, "MAX_HTML", 64)
    with pytest.raises(ValueError, match="bounded size"):
        news.decode_html(gzip.compress(b"A" * 65))


def test_robots_disallow_is_enforced():
    robot = urllib.robotparser.RobotFileParser()
    robot.parse(["User-agent: *", "Disallow: /article/"])
    with pytest.raises(ValueError, match="disallows"):
        news.check_policy("https://fixture.example/article/a", {"fixture.example": robot})


def test_acquisition_pins_raw_and_linked_sections_and_quarantines_time(tmp_path, monkeypatch):
    raw = html('<meta property="article:published_time" content="2024-04-03T09:30:00+07:00">')
    calls = []

    def fetch(url, *args, **kwargs):
        calls.append(url)
        return raw, {"retrieved_at": "2026-10-18T01:00:00+00:00", "http_status": 200}

    monkeypatch.setattr(news, "fetch_public", fetch)
    monkeypatch.setattr(news, "fetch_policies", lambda *args: ({}, []))
    store = SnapshotStore(tmp_path / "raw")
    listing_hash = store.put_blob(b"synthetic listing")
    discovery = {"config": {"sources": [SOURCE], "release_id": "test-fixture",
                             "data_kind": "test_fixture",
                             "ticker_aliases": {"FPT": [], "HPG": ["Hòa Phát"]}},
                 "candidates": [{"record_id": "NEWS-fixture-a", "source_id": "fixture",
                                  "url": "https://fixture.example/article/a",
                                  "listing_url": "https://fixture.example/rss",
                                  "listing_snapshot_hash": listing_hash}]}
    summary = news.acquire(discovery, store=store, output=tmp_path / "first", delay=0)
    assert summary["run_kind"] == "test_fixture"
    assert summary["success_documents"] == 1
    version, = store.versions()
    assert version.data_kind == "test_fixture"
    assert version.media_type == "text/html" and version.related_tickers == ("FPT", "HPG")
    assert version.published_at.isoformat() == "2024-04-03T02:30:00+00:00"
    assert version.available_at is None and version.availability_basis == "unverified"
    assert "availability_unverified" in version.quarantine_reasons("strict")
    assert store.read_blob(version.content_hash) == raw
    page = EvidencePage.model_validate_json((tmp_path / "first/pages.jsonl").read_text(encoding="utf-8"))
    assert page.related_tickers == version.related_tickers
    assert page.text_hash == hashlib.sha256(page.text.encode()).hexdigest()
    assert not deliver_as_of(store, decision_at="2026-10-18T02:00:00Z").deliveries
    reused = news.acquire(discovery, store=store, output=tmp_path / "reused", delay=0, skip_registered=True)
    assert reused["success_documents"] == 1 and len(calls) == 1
    assert len(store.versions()) == 1
    manifest = json.loads((tmp_path / "reused/sources.json").read_text(encoding="utf-8"))
    assert manifest["documents"][0]["related_tickers"] == ["FPT", "HPG"]
    validate_manifest_identity(version, manifest["documents"][0])
    discovery_path = tmp_path / "discovery.json"
    discovery_path.write_text(json.dumps(discovery), encoding="utf-8")
    monkeypatch.setattr(news, "fetch_public", lambda *args, **kwargs: pytest.fail("Offline review attempted HTTP"))
    reviewed = news.reextract(tmp_path / "first/summary.json", discovery_path,
                              store=store, output=tmp_path / "reviewed")
    assert reviewed["network_requests"] == 0 and reviewed["success_documents"] == 1
    assert reviewed["extraction_text_changes"] == []
    assert len(store.versions()) == 1
    reviewed_manifest = json.loads((tmp_path / "reviewed/sources.json").read_text(encoding="utf-8"))
    validate_manifest_identity(version, reviewed_manifest["documents"][0])


def test_empty_rss_stays_failed_and_cannot_inflate_article_count(tmp_path, monkeypatch):
    monkeypatch.setattr(news, "fetch_policies", lambda *args: ({}, []))
    monkeypatch.setattr(news, "fetch_public", lambda *args, **kwargs: (
        b"<rss><channel/></rss>", {"retrieved_at": "2026-10-18T01:00:00Z"}))
    result = news.discover({"sources": [SOURCE], "data_kind": "test_fixture"},
                           store=SnapshotStore(tmp_path / "raw"), output=tmp_path / "discovery", delay=0)
    assert result["candidates"] == []
    assert result["resources"][0]["status"] == "failed"
