"""Loopback dashboard API: existing evidence, gated retrieval, local extraction, market data."""

import json
import re
import threading
from dataclasses import asdict
from datetime import date, datetime
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from starlette.middleware.trustedhost import TrustedHostMiddleware

from pit_haf.data.catalog import Catalog
from pit_haf.data.evidence import aware
from pit_haf.data.gateway import deliver_as_of
from pit_haf.data.snapshots import SnapshotStore
from pit_haf.data.vnstock_provider import MarketDataError, VietnamMarketDataProvider
from pit_haf.llm.ollama import http_request, sha256
from pit_haf.ui.workspace import (
    extract_passage,
    load_corpus,
    load_pilot_metrics,
    search_passages,
    workspace_fingerprint,
)


class SearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    query: str = Field(min_length=2, max_length=300)
    ticker: str | None = Field(default=None, pattern=r"^[A-Z0-9]{2,12}$")
    mode: Literal["exploratory_current", "strict_point_in_time"] = "exploratory_current"
    decision_at: datetime | None = None

    @field_validator("decision_at")
    @classmethod
    def explicit_timezone(cls, value):
        return aware(value, "decision_at") if value else None

    @model_validator(mode="after")
    def historical_cutoff(self):
        if self.mode == "strict_point_in_time" and self.decision_at is None:
            raise ValueError("Chế độ Point-in-Time cần thời điểm có múi giờ.")
        return self


class AnalysisRequest(SearchRequest):
    version_id: str
    page: int = Field(ge=1)
    start: int = Field(ge=0)


def create_app(root: Path | None = None) -> FastAPI:
    root = root or Path(__file__).resolve().parents[3]
    app = FastAPI(title="PiT-HAF workspace", docs_url="/api/docs", redoc_url=None)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["localhost", "127.0.0.1", "testserver"])
    model_lock = threading.Lock()
    corpus_lock = threading.Lock()
    cache = {"fingerprint": None, "corpus": None}
    disk_cache = {"fingerprint": None, "catalog": None}

    def disk_catalog():
        paths = sorted(root.glob("outputs/milestone-1/data-pilot/*/summary.json"),
                       key=lambda p: p.stat().st_mtime_ns, reverse=True)
        if not paths or not (paths[0].parent / "catalog.json").is_file():
            return None
        summary = paths[0]
        pointer = summary.parent / "catalog.json"
        try:
            name = json.loads(pointer.read_text(encoding="utf-8"))["catalog_file"]
            if Path(name).name != name:
                raise ValueError("Invalid catalog locator")
            files = [summary, pointer, summary.parent / name]
            fingerprint = tuple((str(p), p.stat().st_mtime_ns, p.stat().st_size) for p in files)
        except (OSError, ValueError, KeyError) as exc:
            raise HTTPException(503, "Không mở được catalog: " + str(exc)) from exc
        with corpus_lock:
            if fingerprint != disk_cache["fingerprint"]:
                try:
                    catalog = Catalog(root, summary)
                except (OSError, ValueError, KeyError) as exc:
                    raise HTTPException(503, "Không mở được catalog: " + str(exc)) from exc
                disk_cache.update(fingerprint=fingerprint, catalog=catalog)
        return disk_cache["catalog"]

    @app.middleware("http")
    async def local_origin(request: Request, call_next):
        origin = request.headers.get("origin")
        if request.method == "POST" and origin:
            parsed = urlsplit(origin)
            if parsed.scheme != "http" or parsed.netloc != request.headers.get("host"):
                return JSONResponse({"detail": "Chỉ chấp nhận thao tác từ giao diện local."}, 403)
        return await call_next(request)

    def corpus():
        fingerprint = workspace_fingerprint(root)
        with corpus_lock:
            if fingerprint != cache["fingerprint"] or cache["corpus"] is None:
                cache.update(fingerprint=fingerprint, corpus=load_corpus(root))
            return cache["corpus"]

    def retrieve(body: SearchRequest):
        catalog = disk_catalog()
        data = None if catalog else corpus()
        if data is not None and data.errors:
            raise HTTPException(503, detail="; ".join(data.errors))
        allowed, audit = None, []
        if body.mode == "strict_point_in_time":
            gate = deliver_as_of(SnapshotStore(root / "data/cache/evidence"),
                                 decision_at=body.decision_at.isoformat())
            allowed = {item.evidence.version_id for item in gate.deliveries}
            audit = list(gate.audit)
        if catalog:
            try:
                data, hits = catalog.search(body.query, ticker=body.ticker, allowed_versions=allowed)
            except (OSError, ValueError) as exc:
                raise HTTPException(503, "Bằng chứng không còn toàn vẹn: " + str(exc)) from exc
        else:
            hits = search_passages(data, body.query, ticker=body.ticker, allowed_versions=allowed)
        return data, hits, allowed, audit

    @app.get("/api/health")
    def health():
        return {"status": "ok", "application": "pit-haf", "interface": "react"}

    @app.get("/api/workspace")
    def workspace(ticker: str | None = None):
        catalog = disk_catalog()
        if catalog:
            facets = catalog.facets()
            stats = catalog.stats()
            scoped = catalog.stats(ticker)
            coverage = None
            for path in sorted(root.glob("data/corpus/*/coverage.json"), reverse=True):
                report = json.loads(path.read_text(encoding="utf-8"))
                if report.get("summary_sha256") == catalog.pointer["summary_sha256"]:
                    coverage = report
                    break
            return {"documents": catalog.browse(ticker=ticker)["documents"], "errors": [],
                    "snapshot": catalog.snapshot, "coverage": coverage,
                    "document_count": stats["documents"], "page_count": stats["pages"],
                    "text_page_count": stats["text_pages"], "pdf_page_count": stats.get("pdf_pages", 0),
                    "article_count": stats.get("articles", 0), "dataset_article_count": stats.get("dataset_articles", 0),
                    "html_article_count": stats.get("articles", 0) - stats.get("dataset_articles", 0),
                    "pilot": load_pilot_metrics(root),
                    "catalog": {"facets": facets, "stats": stats, "scope_stats": scoped,
                                "scope_ticker": ticker or "all",
                                "breakdown": [{"ticker": t, **catalog.stats(t)} for t in facets["tickers"]],
                                "retrieval_method": "SQLite FTS5 current-corpus BM25; strict cohort uses filtered literal BM25"}}
        data = corpus()
        versions = []
        for item in data.versions:
            pages = [page for page in data.pages if page.version_id == item.version_id]
            diagnostics = next((row for row in data.document_diagnostics
                                if row.get("version_id") == item.version_id), {})
            versions.append({**item.model_dump(mode="json"), "pages": len(pages),
                             "text_pages": sum(bool(page.text.strip()) for page in pages),
                             "parser_warning_count": diagnostics.get("parser_warning_count"),
                             "potentially_partial_text_pages": diagnostics.get(
                                 "potentially_partial_text_pages", []),
                             "potentially_partial_document": diagnostics.get(
                                 "potentially_partial_document", False),
                             "quarantine_reasons": item.quarantine_reasons("strict")})
        coverage = None
        if data.snapshot:
            summary_hash = sha256((root / data.snapshot).read_bytes())
            for path in sorted(root.glob("data/corpus/*/coverage.json"), reverse=True):
                try:
                    report = json.loads(path.read_text(encoding="utf-8"))
                    if report.get("summary_sha256") == summary_hash:
                        coverage = report
                        break
                except (OSError, ValueError):
                    continue
        return {"documents": versions, "errors": data.errors, "snapshot": data.snapshot,
                "coverage": coverage,
                "page_count": len(data.pages),
                "text_page_count": sum(bool(page.text.strip()) for page in data.pages),
                "pdf_page_count": sum(v["pages"] for v in versions if v["media_type"] == "application/pdf"),
                "html_article_count": sum(v["media_type"] == "text/html" for v in versions),
                "pilot": load_pilot_metrics(root)}

    @app.get("/api/catalog/documents")
    def catalog_documents(offset: int = Query(0, ge=0), limit: int = Query(20, ge=1, le=100),
                          q: str = Query("", max_length=300), ticker: str | None = None,
                          kind: str | None = None, year: str | None = None, scope: str | None = None,
                          publisher: str | None = None, origin: str | None = None):
        catalog = disk_catalog()
        if catalog is None:
            raise HTTPException(404, "Snapshot hiện tại chưa có catalog trên đĩa.")
        return {**catalog.browse(offset=offset, limit=limit, q=q, ticker=ticker, kind=kind,
                                year=year, scope=scope, publisher=publisher, origin=origin),
                "stats": catalog.stats(ticker)}

    @app.get("/api/documents/{version_id}/pages/{page_number}")
    def page_text(version_id: str, page_number: int):
        catalog = disk_catalog()
        if catalog:
            try:
                return catalog.page(version_id, page_number)[1].model_dump(mode="json")
            except KeyError as exc:
                raise HTTPException(404, "Không tìm thấy trang tài liệu.") from exc
            except (OSError, ValueError) as exc:
                raise HTTPException(503, "Bằng chứng không còn toàn vẹn: " + str(exc)) from exc
        page = next((item for item in corpus().pages if item.version_id == version_id
                     and item.page == page_number), None)
        if page is None:
            raise HTTPException(404, "Không tìm thấy trang tài liệu.")
        return page.model_dump(mode="json")

    @app.get("/api/model")
    def model_status():
        try:
            version = http_request("http://127.0.0.1:11434/api/version", None, 2)
            tags = http_request("http://127.0.0.1:11434/api/tags", None, 2)
            if version.status != 200 or tags.status != 200:
                raise ValueError("Ollama không trả trạng thái hợp lệ.")
            models = json.loads(tags.body).get("models", [])
            candidate = next((item for item in models if item.get("name") == "qwen3:4b"), None)
            return {"connected": True, "version": json.loads(version.body)["version"],
                    "model": "qwen3:4b", "installed": candidate is not None,
                    "digest": candidate.get("digest") if candidate else None}
        except (OSError, ValueError, KeyError) as exc:
            return {"connected": False, "installed": False, "error": str(exc)}

    @app.post("/api/search")
    def search(body: SearchRequest):
        _, hits, allowed, audit = retrieve(body)
        return {"passages": [asdict(hit) for hit in hits], "mode": body.mode,
                "allowed_versions": len(allowed) if allowed is not None else None,
                "gateway_audit": audit, "historical_availability_validated": allowed is not None,
                "retrieval_method": ("SQLite FTS5 BM25; current catalog only" if disk_catalog() and allowed is None
                                     else "BM25; statistics computed after gateway filtering")}

    @app.post("/api/analysis")
    def analysis(body: AnalysisRequest):
        data, hits, allowed, audit = retrieve(body)
        hit = next((item for item in hits if (item.version_id, item.page, item.start)
                    == (body.version_id, body.page, body.start)), None)
        if hit is None:
            raise HTTPException(409, "Đoạn đã chọn không còn nằm trong kết quả hợp lệ. Tìm lại trước.")
        if not model_lock.acquire(blocking=False):
            raise HTTPException(409, "Ollama đang xử lý một yêu cầu. Hãy đợi hoàn tất.")
        try:
            return extract_passage(data, hit, root / "outputs/interactive-analysis", mode=body.mode,
                                   decision_at=body.decision_at.isoformat() if body.decision_at
                                   else None, allowed_versions=allowed, retrieval={
                                       "query": body.query, "ticker": body.ticker,
                                       "method": ("sqlite_fts5_current_catalog_v1" if disk_catalog() and allowed is None
                                                  else "bm25_literal_chunks_v0.1"),
                                       "gateway_audit_evaluator_only": audit,
                                       "ranked_passages": [{
                                           "version_id": item.version_id, "page": item.page,
                                           "start": item.start, "end": item.end, "score": item.score,
                                           "context_sha256": sha256(item.text.encode()),
                                       } for item in hits],
                                   })
        finally:
            model_lock.release()

    @app.get("/api/market")
    def market(ticker: str, start: date, end: date, include_index: bool = False):
        if not re.fullmatch(r"[A-Z0-9]{2,12}", ticker):
            raise HTTPException(422, "Mã cổ phiếu không hợp lệ.")
        if start > end:
            raise HTTPException(422, "Ngày bắt đầu phải trước hoặc bằng ngày kết thúc.")
        provider = VietnamMarketDataProvider()
        try:
            prices = provider.get_prices(ticker, start.isoformat(), end.isoformat())
        except (MarketDataError, ValueError) as exc:
            raise HTTPException(502, f"Không tải được dữ liệu: {exc}") from exc
        result = {"ticker": ticker, "prices": json.loads(prices.to_json(orient="records",
                  date_format="iso")), "metadata": prices.attrs, "index": None,
                  "index_error": None, "historical_availability_validated": False}
        if include_index:
            try:
                index = provider.get_prices("VNINDEX", start.isoformat(), end.isoformat(),
                                            asset_type="index")
                result["index"] = json.loads(index.to_json(orient="records", date_format="iso"))
            except (MarketDataError, ValueError) as exc:
                result["index_error"] = str(exc)
        return result

    dist = root / "frontend/dist"
    if (dist / "assets").is_dir():
        app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

    @app.get("/")
    def frontend():
        if not (dist / "index.html").is_file():
            raise HTTPException(503, "Chưa build frontend. Xem README để chạy pnpm build.")
        return FileResponse(dist / "index.html", headers={"Cache-Control": "no-cache"})

    return app


app = create_app()
