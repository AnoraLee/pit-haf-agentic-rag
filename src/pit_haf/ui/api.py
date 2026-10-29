"""Loopback dashboard API: existing evidence, gated retrieval, local extraction, market data."""

import json
import re
import sqlite3
import threading
from dataclasses import asdict
from datetime import date, datetime
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from starlette.middleware.trustedhost import TrustedHostMiddleware

from pit_haf.data.catalog import Catalog
from pit_haf.data.evidence import aware
from pit_haf.data.financial_sections import search_financial
from pit_haf.data.gateway import deliver_as_of
from pit_haf.data.retrieval_scope import resolve_scope
from pit_haf.data.snapshots import SnapshotStore
from pit_haf.data.vnstock_provider import MarketDataError, VietnamMarketDataProvider
from pit_haf.llm.ollama import http_request, sha256
from pit_haf.research.evaluation import evaluate_batch
from pit_haf.research.reports import protocol, report_history, run_report, saved_report
from pit_haf.research.reviews import (
    ReviewConflict,
    ReviewInput,
    active_pack,
    case_detail,
    export_reviews,
    list_cases,
    save_review,
)
from pit_haf.research.source_audit import load_source_audit
from pit_haf.research.table_evidence import run as run_table_evidence
from pit_haf.research.table_reviews import TableReviewInput
from pit_haf.research.table_reviews import save as save_table_review
from pit_haf.research.table_reviews import state as table_review_state
from pit_haf.research.table_views import detail as table_detail
from pit_haf.research.table_views import history as table_history
from pit_haf.research.table_views import page_image as table_page_image
from pit_haf.ui.workspace import (
    Corpus,
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


class CompanyReportRequest(SearchRequest):
    ticker: str = Field(pattern=r"^[A-Z0-9]{2,12}$")
    reporting_period: str | None = Field(default=None, pattern=r"^(?:(?:19|20)\d{2}(?:-Q[1-4])?|all)$")
    source_policy: Literal["issuer_reports", "all_linked"] = "issuer_reports"
    statement_scope: Literal["all", "consolidated", "parent"] = "all"
    retrieval_profile: Literal["lexical_v0.2", "financial_sections_v0.3"] = "lexical_v0.2"


class TableEvidenceRequest(SearchRequest):
    ticker: str = Field(pattern=r"^[A-Z0-9]{2,12}$")
    reporting_period: str | None = Field(default=None, pattern=r"^(?:19|20)\d{2}$")
    profile_id: Literal["table_cells_v0.4", "table_cells_v0.5", "table_cells_v0.6", "table_cells_v0.7"] = "table_cells_v0.6"
    use_model: bool = False


def create_app(root: Path | None = None) -> FastAPI:
    root = root or Path(__file__).resolve().parents[3]
    app = FastAPI(title="PiT-HAF workspace", docs_url="/api/docs", redoc_url=None)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["localhost", "127.0.0.1", "testserver"])
    model_lock = threading.Lock()
    review_lock = threading.Lock()
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

    def retrieve(body: SearchRequest, scope=None, retrieval_trace=None):
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
                if getattr(body, "retrieval_profile", "lexical_v0.2") == "financial_sections_v0.3":
                    data, hits, trace = search_financial(catalog, body.query, scope=scope, allowed_versions=allowed)
                    if retrieval_trace is not None:
                        retrieval_trace.update(trace)
                else:
                    data, hits = catalog.search(body.query, ticker=body.ticker, allowed_versions=allowed, scope=scope)
            except (OSError, ValueError) as exc:
                raise HTTPException(503, "Bằng chứng không còn toàn vẹn: " + str(exc)) from exc
        else:
            if getattr(body, "retrieval_profile", "lexical_v0.2") != "lexical_v0.2":
                raise HTTPException(503, "Cách tìm theo mục báo cáo cần disk catalog. Khôi phục dữ liệu trước.")
            if scope:
                versions = tuple(v for v in data.versions if scope.matches(v) and (allowed is None or v.version_id in allowed))
                ids = {v.version_id for v in versions}
                data = Corpus(versions, tuple(p for p in data.pages if p.version_id in ids),
                              snapshot=data.snapshot, document_diagnostics=data.document_diagnostics)
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

    @app.get("/api/documents/{version_id}/raw")
    def raw_document(version_id: str):
        catalog = disk_catalog()
        try:
            version = catalog.page(version_id, 1)[0] if catalog else next(
                v for v in corpus().versions if v.version_id == version_id)
            if version.media_type != "application/pdf":
                raise HTTPException(415, "Chỉ mở PDF qua đường dẫn này.")
            store = SnapshotStore(root / "data/cache/evidence")
            store.read_blob(version.content_hash)
            return FileResponse(store.blob_path(version.content_hash), media_type="application/pdf",
                                headers={"Content-Disposition": f'inline; filename="{version.content_hash}.pdf"'})
        except (KeyError, StopIteration) as exc:
            raise HTTPException(404, "Không tìm thấy phiên bản PDF.") from exc
        except (OSError, ValueError) as exc:
            raise HTTPException(503, "PDF không còn toàn vẹn: " + str(exc)) from exc

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

    @app.get("/api/research/development")
    def development_status():
        try:
            index, _ = active_pack(root)
        except FileNotFoundError:
            index = None
        return {"protocol": protocol(root), "case_pack": index}

    @app.get("/api/research/cases")
    def development_cases():
        try:
            with review_lock:
                return list_cases(root)
        except (OSError, ValueError, KeyError) as exc:
            raise HTTPException(503, "Không mở được bộ case: " + str(exc)) from exc

    @app.get("/api/research/cases/{case_id}")
    def development_case(case_id: str):
        try:
            with review_lock:
                return case_detail(root, case_id)
        except KeyError as exc:
            raise HTTPException(404, "Không tìm thấy case.") from exc
        except (OSError, ValueError) as exc:
            raise HTTPException(503, "Không mở được nguồn case: " + str(exc)) from exc

    @app.post("/api/research/reviews")
    def development_review(body: ReviewInput):
        try:
            with review_lock:
                return save_review(root, body)
        except ReviewConflict as exc:
            raise HTTPException(409, str(exc)) from exc
        except (OSError, ValueError, KeyError) as exc:
            raise HTTPException(422, str(exc)) from exc

    @app.get("/api/research/reviews/export")
    def development_reviews_export():
        try:
            with review_lock:
                return export_reviews(root)
        except (OSError, ValueError, KeyError) as exc:
            raise HTTPException(503, "Không xuất được annotation: " + str(exc)) from exc

    @app.get("/api/research/evaluation")
    def development_evaluation(batch_id: str | None = Query(default=None, pattern=r"^\d{8}T\d{6}Z-[0-9a-f]{8}$")):
        try:
            with review_lock:
                return evaluate_batch(root, batch_id)
        except (OSError, ValueError, KeyError, TypeError) as exc:
            raise HTTPException(503, "Không đánh giá được bản chạy: " + str(exc)) from exc

    @app.get("/api/research/source-audit")
    def development_source_audit():
        try:
            return {"audit": load_source_audit(root)}
        except (OSError, ValueError, KeyError, TypeError) as exc:
            raise HTTPException(503, "Không mở được bản đối chiếu nguồn: " + str(exc)) from exc

    @app.post("/api/research/report")
    def company_report(body: CompanyReportRequest):
        scope = resolve_scope(body.query, body.ticker, reporting_period=body.reporting_period,
                              source_policy=body.source_policy, statement_scope=body.statement_scope)
        trace = {} if body.retrieval_profile == "financial_sections_v0.3" else None
        data, hits, allowed, audit = retrieve(body, scope=scope, retrieval_trace=trace)
        if not model_lock.acquire(blocking=False):
            raise HTTPException(409, "Ollama đang xử lý một yêu cầu. Hãy đợi hoàn tất.")
        try:
            return run_report(root, data, hits, query=body.query, ticker=body.ticker, mode=body.mode,
                              decision_at=body.decision_at.isoformat() if body.decision_at else None,
                              allowed_versions=allowed, retrieval_audit=audit, scope=scope, retrieval_trace=trace)
        except (OSError, ValueError) as exc:
            raise HTTPException(503, "Không lập được báo cáo: " + str(exc)) from exc
        finally:
            model_lock.release()

    @app.get("/api/research/reports")
    def company_report_history():
        return {"reports": report_history(root)}

    @app.get("/api/research/table-evidence")
    def table_runs(ticker: str | None = Query(default=None, pattern=r"^[A-Z0-9]{2,12}$")):
        return {"runs": table_history(root, ticker)}

    @app.post("/api/research/table-evidence")
    def create_table_run(body: TableEvidenceRequest):
        if not model_lock.acquire(blocking=False):
            raise HTTPException(409, "Một tác vụ phân tích đang chạy. Hãy đợi hoàn tất.")
        try:
            _, result = run_table_evidence(root, query=body.query, ticker=body.ticker, mode=body.mode,
                                          decision_at=body.decision_at.isoformat() if body.decision_at else None,
                                          reporting_period=body.reporting_period, use_model=body.use_model,
                                          profile_id=body.profile_id)
            if result["status"] == "failed":
                raise HTTPException(503, f"Không hoàn tất đọc bảng. Lượt lỗi đã lưu: {result['run_id']}.")
            return reviewed_table_detail(result["run_id"])
        except (OSError, ValueError, KeyError, TypeError, sqlite3.Error) as exc:
            raise HTTPException(503, "Không đọc được bằng chứng theo ô: " + str(exc)) from exc
        finally:
            model_lock.release()

    def reviewed_table_detail(run_id):
        view = table_detail(root, run_id)
        return {**view, "reviews": table_review_state(root, view)}

    @app.get("/api/research/table-evidence/{run_id}")
    def saved_table_run(run_id: str):
        try:
            return reviewed_table_detail(run_id)
        except FileNotFoundError as exc:
            raise HTTPException(404, "Không tìm thấy lượt đọc bảng.") from exc
        except (OSError, ValueError, KeyError, TypeError, sqlite3.Error) as exc:
            raise HTTPException(503, "Không mở được lượt đọc bảng toàn vẹn: " + str(exc)) from exc

    @app.post("/api/research/table-evidence/{run_id}/reviews")
    def table_review(run_id: str, body: TableReviewInput):
        if run_id != body.run_id:
            raise HTTPException(422, "Mã lượt chạy trong đường dẫn và đánh giá không khớp.")
        try:
            view = table_detail(root, run_id)
            table_review_state(root, view)
        except FileNotFoundError as exc:
            raise HTTPException(404, "Không tìm thấy lượt đọc bảng.") from exc
        except (OSError, ValueError, KeyError, TypeError, sqlite3.Error) as exc:
            raise HTTPException(503, "Nguồn hoặc lịch sử đánh giá không còn toàn vẹn: " + str(exc)) from exc
        try:
            return save_table_review(root, view, body)
        except ReviewConflict as exc:
            raise HTTPException(409, "Đánh giá hoặc nguồn đã thay đổi. Tải lại trước khi lưu: " + str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(422, "Chưa lưu đánh giá: " + str(exc)) from exc
        except (OSError, sqlite3.Error) as exc:
            raise HTTPException(503, "Không lưu được đánh giá: " + str(exc)) from exc

    @app.get("/api/research/table-evidence/{run_id}/reviews/export")
    def table_review_export(run_id: str):
        data = saved_table_run(run_id)
        return JSONResponse(data["reviews"], headers={
            "Content-Disposition": f'attachment; filename="table-reviews-{run_id}.json"',
            "Cache-Control": "no-store"})

    @app.get("/api/research/table-evidence/{run_id}/pages/{index}/image")
    def table_source_image(run_id: str, index: int):
        try:
            return Response(table_page_image(root, run_id, index), media_type="image/png",
                            headers={"Cache-Control": "no-store"})
        except (FileNotFoundError, KeyError, IndexError) as exc:
            raise HTTPException(404, "Không tìm thấy trang PDF của lượt đọc bảng.") from exc
        except (OSError, ValueError, TypeError) as exc:
            raise HTTPException(503, "Không render được PDF toàn vẹn: " + str(exc)) from exc

    @app.get("/api/research/reports/{run_id}")
    def company_saved_report(run_id: str):
        try:
            return saved_report(root, run_id)
        except FileNotFoundError as exc:
            raise HTTPException(404, "Không tìm thấy báo cáo đã hoàn tất.") from exc
        except (OSError, ValueError, KeyError) as exc:
            raise HTTPException(503, "Không đọc được báo cáo toàn vẹn: " + str(exc)) from exc

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
