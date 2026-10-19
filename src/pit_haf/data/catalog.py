"""Checksummed disk catalog: bounded browsing and literal FTS retrieval for large corpora."""

import argparse
import hashlib
import json
import sqlite3
from collections import Counter
from functools import lru_cache
from pathlib import Path

from pit_haf.data.evidence import EvidencePage, EvidenceVersion
from pit_haf.data.hub import file_sha
from pit_haf.data.snapshots import SnapshotError, SnapshotStore
from pit_haf.ui.workspace import Corpus, Passage, search_passages, tokens


def chunks(text):
    start = 0
    while start < len(text):
        end = min(start + 900, len(text))
        if end < len(text):
            boundary = text.rfind(" ", start + 500, end)
            if boundary > start:
                end = boundary
        yield start, end, text[start:end]
        if end == len(text):
            break
        start = max(start + 1, end - 120)


def build_catalog(summary_path: Path, *, store: SnapshotStore, output: Path) -> dict:
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    pages_path = summary_path.parent / "pages.jsonl"
    if file_sha(pages_path) != summary["pages_sha256"]:
        raise SnapshotError("Catalog input pages checksum mismatch")
    accepted = {r["version_id"]: r for r in summary["documents"] if r["status"] == "extracted"}
    versions = {v.version_id: v for v in store.versions() if v.version_id in accepted}
    if set(versions) != set(accepted) or any(v.data_kind != "real_document" for v in versions.values()):
        raise SnapshotError("Catalog input contains missing versions or fixtures")
    if output.exists():
        raise FileExistsError(output)
    with store._connect() as db:
        registry_hashes = dict(db.execute("SELECT version_id,metadata_hash FROM versions"))
    output.parent.mkdir(parents=True, exist_ok=True)
    counts = Counter()
    with sqlite3.connect(output) as db:
        db.executescript("""
            PRAGMA journal_mode=DELETE;
            CREATE TABLE documents(version_id TEXT PRIMARY KEY,ticker TEXT,publisher TEXT,
              kind TEXT,year TEXT,scope TEXT,origin TEXT,title TEXT,sort_date TEXT,search_text TEXT,
              metadata_json TEXT,registry_hash TEXT,pages INTEGER,text_pages INTEGER,diagnostics_json TEXT);
            CREATE INDEX document_filter ON documents(ticker,kind,year,publisher);
            CREATE TABLE links(version_id TEXT,ticker TEXT,PRIMARY KEY(version_id,ticker));
            CREATE INDEX ticker_links ON links(ticker,version_id);
            CREATE TABLE pages(version_id TEXT,page INTEGER,page_json TEXT,PRIMARY KEY(version_id,page));
            CREATE VIRTUAL TABLE passages USING fts5(search_text,text UNINDEXED,version_id UNINDEXED,
              record_id UNINDEXED,ticker UNINDEXED,page UNINDEXED,start UNINDEXED,end UNINDEXED,
              page_text_hash UNINDEXED,tokenize='unicode61');
        """)
        for version in versions.values():
            store.read_blob(version.content_hash)
            row = accepted[version.version_id]
            metadata = version.model_dump(mode="json")
            diagnostics = {k: row.get(k) for k in (
                "parser_warning_count", "potentially_partial_text_pages", "potentially_partial_document")}
            search_text = " ".join(tokens(" ".join(filter(None, (
                version.title, version.ticker, version.publisher, version.reporting_period,
                " ".join(version.related_tickers))))))
            db.execute("INSERT INTO documents VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (
                version.version_id, version.ticker, version.publisher or "Báo cáo doanh nghiệp",
                version.document_type, (version.reporting_period or "")[:4], version.statement_scope,
                version.origin, version.title, str(version.publication_date or version.reporting_period or ""),
                search_text, json.dumps(metadata, ensure_ascii=False), registry_hashes[version.version_id],
                row["pages"], row["text_pages"], json.dumps(diagnostics)))
            db.executemany("INSERT INTO links VALUES (?,?)", [
                (version.version_id, ticker) for ticker in sorted({version.ticker, *version.related_tickers})])
        with pages_path.open("rb") as stream:
            for line in stream:
                if not line.strip():
                    continue
                page = EvidencePage.model_validate_json(line)
                version = versions.get(page.version_id)
                if (version is None or page.record_id != version.record_id or page.ticker != version.ticker or
                        page.content_hash != version.content_hash or page.source_url != version.source_url or
                        page.related_tickers != version.related_tickers or page.data_kind != version.data_kind or
                        page.retrieved_at != version.retrieved_at or
                        hashlib.sha256(page.text.encode()).hexdigest() != page.text_hash):
                    raise SnapshotError("Catalog page identity or checksum mismatch")
                db.execute("INSERT INTO pages VALUES (?,?,?)", (page.version_id, page.page, line.decode().strip()))
                counts[page.version_id] += 1
                for start, end, text in chunks(page.text):
                    indexed = " ".join(tokens(text))
                    if indexed:
                        db.execute("INSERT INTO passages VALUES (?,?,?,?,?,?,?,?,?)", (
                            indexed, text, page.version_id, page.record_id, page.ticker,
                            page.page, start, end, page.text_hash))
        if sum(counts.values()) != summary["page_count"] or any(
            counts[v] != accepted[v]["pages"] for v in accepted
        ):
            raise SnapshotError("Catalog page coverage mismatch")
        db.execute("INSERT INTO passages(passages) VALUES('optimize')")
        db.execute("PRAGMA optimize")
    pointer = {"schema_version": "disk_catalog_v1", "summary_sha256": file_sha(summary_path),
               "pages_sha256": summary["pages_sha256"], "catalog_file": output.name,
               "catalog_sha256": file_sha(output), "documents": len(versions),
               "research_prediction_results": False}
    return pointer


class Catalog:
    def __init__(self, root: Path, summary_path: Path):
        root, summary_path = root.resolve(), summary_path.resolve()
        self.root, self.summary_path = root, summary_path
        self.snapshot = str(summary_path.relative_to(root))
        self.pointer = json.loads((summary_path.parent / "catalog.json").read_text(encoding="utf-8"))
        name = self.pointer["catalog_file"]
        if Path(name).name != name:
            raise SnapshotError("Catalog locator must stay within its snapshot folder")
        self.path = summary_path.parent / name
        if (file_sha(summary_path) != self.pointer["summary_sha256"] or
                file_sha(self.path) != self.pointer["catalog_sha256"]):
            raise SnapshotError("Catalog/summary checksum mismatch")
        self.store = SnapshotStore(root / "data/cache/evidence")

    def connect(self):
        db = sqlite3.connect(self.path.resolve().as_uri() + "?mode=ro", uri=True)
        db.row_factory = sqlite3.Row
        return db

    @staticmethod
    def filters(ticker=None, q="", kind=None, year=None, scope=None, publisher=None, origin=None):
        clauses, params = ["1=1"], []
        if ticker and ticker != "all":
            clauses.append("EXISTS(SELECT 1 FROM links l WHERE l.version_id=d.version_id AND l.ticker=?)")
            params.append(ticker)
        for column, value in (("kind", kind), ("year", year), ("scope", scope), ("publisher", publisher), ("origin", origin)):
            if value and value != "all":
                clauses.append("d." + column + "=?")
                params.append(value)
        if q.strip():
            clauses.append("instr(d.search_text,?)>0")
            params.append(" ".join(tokens(q)))
        return " AND ".join(clauses), params

    @staticmethod
    def document(row):
        data = json.loads(row["metadata_json"])
        version = EvidenceVersion.model_validate(data)
        return {**data, "pages": row["pages"], "text_pages": row["text_pages"],
                **json.loads(row["diagnostics_json"]), "quarantine_reasons": version.quarantine_reasons("strict")}

    @lru_cache(maxsize=256)
    def stats(self, ticker=None):
        where, params = self.filters(ticker=ticker)
        with self.connect() as db:
            rows = db.execute("SELECT metadata_json,pages,text_pages FROM documents d WHERE " + where, params)
            total = Counter()
            for row in rows:
                data = json.loads(row["metadata_json"])
                total["documents"] += 1
                total["pages"] += row["pages"]
                total["text_pages"] += row["text_pages"]
                total["with_text"] += bool(row["text_pages"])
                total["quarantined"] += bool(EvidenceVersion.model_validate(data).quarantine_reasons("strict"))
                if data["media_type"] == "application/pdf":
                    total["pdf_documents"] += 1
                    total["pdf_pages"] += row["pages"]
                    total["pdf_text_pages"] += row["text_pages"]
                    total["ocr_backlog"] += row["pages"] - row["text_pages"]
                else:
                    total["articles"] += 1
                    total["dataset_articles"] += data.get("origin") == "dataset_mirror"
        return dict(total)

    def browse(self, *, offset=0, limit=20, **filters):
        where, params = self.filters(**filters)
        with self.connect() as db:
            total = db.execute("SELECT COUNT(*) FROM documents d WHERE " + where, params).fetchone()[0]
            rows = db.execute("SELECT * FROM documents d WHERE " + where +
                              " ORDER BY sort_date DESC,ticker,title,version_id LIMIT ? OFFSET ?",
                              [*params, limit, offset]).fetchall()
        return {"documents": [self.document(row) for row in rows], "total": total,
                "offset": offset, "limit": limit}

    @lru_cache(maxsize=1)
    def facets(self):
        with self.connect() as db:
            result = {key: [r[0] for r in db.execute(f"SELECT DISTINCT {column} FROM documents WHERE {column}<>'' ORDER BY {column}")]
                      for key, column in (("types", "kind"), ("years", "year"), ("publishers", "publisher"), ("origins", "origin"))}
            result["tickers"] = [r[0] for r in db.execute("SELECT DISTINCT ticker FROM links ORDER BY ticker")]
        return result

    def page(self, version_id, number):
        with self.connect() as db:
            row = db.execute("SELECT * FROM documents WHERE version_id=?", (version_id,)).fetchone()
            source = db.execute("SELECT page_json FROM pages WHERE version_id=? AND page=?", (version_id, number)).fetchone()
        if row is None or source is None:
            raise KeyError("Unknown catalog page")
        with self.store._connect() as db:
            original = db.execute("SELECT metadata_json,metadata_hash FROM versions WHERE version_id=?", (version_id,)).fetchone()
        if original is None or original["metadata_hash"] != row["registry_hash"] or hashlib.sha256(original["metadata_json"].encode()).hexdigest() != row["registry_hash"]:
            raise SnapshotError("Catalog and immutable registry disagree")
        version = EvidenceVersion.model_validate_json(row["metadata_json"])
        self.store.read_blob(version.content_hash)
        page = EvidencePage.model_validate_json(source[0])
        if hashlib.sha256(page.text.encode()).hexdigest() != page.text_hash:
            raise SnapshotError("Catalog literal text checksum mismatch")
        return version, page, json.loads(row["diagnostics_json"])

    def subset(self, identities):
        versions, pages, diagnostics = {}, {}, {}
        for version_id, number in sorted(set(identities)):
            version, page, diagnostic = self.page(version_id, number)
            versions[version_id] = version
            pages[(version_id, number)] = page
            diagnostics[version_id] = {"version_id": version_id, **diagnostic}
        return Corpus(tuple(versions.values()), tuple(pages.values()), snapshot=self.snapshot,
                      document_diagnostics=tuple(diagnostics.values()))

    def search(self, query, *, ticker=None, allowed_versions=None, limit=6, scope=None):
        scope_where, scope_params = scope.sql() if scope else ("1=1", [])
        if allowed_versions is not None:
            identities = []
            with self.connect() as db:
                # Intersect metadata before reading pages or computing historical statistics.
                scoped_ids = {r[0] for r in db.execute("SELECT version_id FROM documents d WHERE " + scope_where, scope_params)}
                for version_id in sorted(allowed_versions & scoped_ids):
                    identities.extend((version_id, row[0]) for row in db.execute("SELECT page FROM pages WHERE version_id=?", (version_id,)))
            subset = self.subset(identities)
            return subset, search_passages(subset, query, ticker=ticker, allowed_versions=allowed_versions, limit=limit)
        terms = sorted(set(tokens(query)))[:40]
        if not terms:
            return Corpus(snapshot=self.snapshot), []
        expression = " OR ".join('"' + term + '"' for term in terms)
        clause = " AND EXISTS(SELECT 1 FROM links l WHERE l.version_id=passages.version_id AND l.ticker=?)" if ticker else ""
        if scope:
            clause += " AND EXISTS(SELECT 1 FROM documents d WHERE d.version_id=passages.version_id AND " + scope_where + ")"
        with self.connect() as db:
            rows = db.execute("SELECT *,bm25(passages) score FROM passages WHERE passages MATCH ?" + clause +
                              " ORDER BY score,version_id,page,start LIMIT ?", [expression, *([ticker] if ticker else []), *scope_params, limit]).fetchall()
        hits = [Passage(r["version_id"], r["record_id"], r["ticker"], int(r["page"]), int(r["start"]),
                        int(r["end"]), r["text"], r["page_text_hash"], -r["score"]) for r in rows]
        subset = self.subset((h.version_id, h.page) for h in hits)
        for hit in hits:
            source = next(p for p in subset.pages if p.version_id == hit.version_id and p.page == hit.page)
            if source.text[hit.start:hit.end] != hit.text:
                raise SnapshotError("FTS passage offsets disagree with literal source")
        return subset, hits


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--summary", type=Path, required=True)
    parser.add_argument("--root", type=Path, default=Path("data/cache/evidence"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    pointer = build_catalog(args.summary, store=SnapshotStore(args.root), output=args.output)
    (args.output.parent / "catalog.json").write_text(json.dumps(pointer, indent=2), encoding="utf-8")
    print(json.dumps(pointer))


if __name__ == "__main__":
    main()
