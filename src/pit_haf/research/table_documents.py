"""Metadata-only document preview and explicit annual scope for table reading."""

import re

from pit_haf.data.financial_sections import normalized
from pit_haf.data.pdf_text import settings as text_settings
from pit_haf.data.retrieval_scope import DocumentReportScope, resolve_scope
from pit_haf.research.reports import retrieval_access


def annual_scope(query, ticker, *, reporting_period=None, version_id=None):
    scope = resolve_scope(query, ticker, reporting_period=reporting_period,
                          source_policy="issuer_reports", statement_scope="all")
    if (not re.fullmatch(r"(?:19|20)\d{2}", scope.reporting_period or "") or
            re.search(r"\b(?:quy\s*(?:iv|iii|ii|i|[1-4])|q[1-4]|quarter\s*[1-4])\b", normalized(query))):
        raise ValueError("Table reading requires an explicit annual period YYYY; quarter columns are unsupported")
    return DocumentReportScope(**scope.model_dump(), version_id=version_id) if version_id is not None else scope


def document_options(catalog, *, query, ticker, reporting_period=None, profile_id,
                     mode="exploratory_current", decision_at=None):
    # Only the version metadata is read. An empty temporal allowlist never opens the catalog.
    if profile_id not in {f"table_cells_v0.{n}" for n in range(4, 10)}:
        raise ValueError("Unknown table evidence profile")
    scope = annual_scope(query, ticker, reporting_period=reporting_period)
    allowed, _ = retrieval_access(catalog.root, mode, decision_at)
    budget = (text_settings(catalog.root)["max_reparsed_pages"]
              if profile_id in {"table_cells_v0.7", "table_cells_v0.8", "table_cells_v0.9"} else None)
    documents = []
    if allowed is None or allowed:
        where, params = scope.sql()
        with catalog.connect() as db:
            rows = db.execute("SELECT * FROM documents d WHERE " + where + " ORDER BY version_id", params)
            for row in rows:
                if allowed is not None and row["version_id"] not in allowed:
                    continue
                document = catalog.document(row)
                documents.append({k: document[k] for k in (
                    "version_id", "title", "ticker", "reporting_period", "statement_scope", "document_type",
                    "pages", "text_pages", "source_url", "content_hash", "quarantine_reasons")})
    pages = sum(d["pages"] for d in documents)
    for document in documents:
        document["within_page_budget"] = budget is None or document["pages"] <= budget
    return {"documents": documents, "scope": scope.model_dump(), "snapshot": catalog.snapshot,
            "mode": mode, "decision_at": decision_at, "profile_id": profile_id,
            "total_pages": pages, "max_reparsed_pages": budget,
            "over_page_budget": budget is not None and pages > budget,
            "selection_basis": "explicit_caller_choice; no automatic document ranking or fallback",
            "text_counts_basis": "legacy_catalog; not a new extraction or OCR assessment",
            "historical_availability_validated": False}
