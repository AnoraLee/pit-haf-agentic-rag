"""Source-bound local OCR review declarations, separate from extraction and answer context."""

import json
import sqlite3
from contextlib import closing
from datetime import UTC, date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from pit_haf.data.ocr_cells import NUMBER
from pit_haf.data.snapshots import canonical
from pit_haf.llm.ollama import sha256
from pit_haf.research.reviews import ReviewConflict
from pit_haf.research.table_reviews import CellChecks

HEX = r"^[a-f0-9]{64}$"
RUN = r"^\d{8}T\d{6}Z-[a-f0-9]{8}$"
PROTOCOL = "ocr_cell_reviews_v0.1"


class OcrInterpretation(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    metric: str = Field(min_length=1, max_length=250)
    value_literal: str = Field(min_length=1, max_length=120)
    year: str = Field(pattern=r"^(?:19|20)\d{2}$")
    unit: str = Field(min_length=1, max_length=100)
    statement_scope: Literal["consolidated", "parent"]

    @field_validator("metric", "value_literal", "unit")
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError("Enter a nonblank reviewed interpretation")
        return value.strip()


class OcrReviewInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    run_id: str = Field(pattern=RUN)
    policy_id: Literal["ocr_cell_links_v0.1", "ocr_cell_links_v0.2"]
    header_run_id: str | None = Field(default=None, pattern=RUN)
    candidate_id: str = Field(pattern=HEX)
    binding_sha256: str = Field(pattern=HEX)
    previous_revision: str | None = Field(default=None, pattern=HEX)
    status: Literal["pending", "needs_context", "rejected", "confirmed"]
    reviewer: str = Field(min_length=1, max_length=100)
    declaration: bool = False
    checks: CellChecks = Field(default_factory=CellChecks)
    interpretation: OcrInterpretation | None = None
    year_method: Literal["explicit_column", "annual_current", "annual_previous"] | None = None
    calendar_mapping_checked: bool = False
    year_basis_note: str = Field(default="", max_length=1000)
    correction_notes: str = Field(default="", max_length=2000)
    notes: str = Field(default="", max_length=3000)

    @field_validator("reviewer")
    @classmethod
    def named_reviewer(cls, value):
        if not value.strip():
            raise ValueError("Enter a reviewer name or initials")
        return value.strip()


def year_options(cell):
    fields = cell["fields"]
    period = fields.get("period") or {}
    kind = period.get("observed_value")
    if kind == "absolute_year" and period.get("observed_year") is not None:
        return {"explicit_column": str(period["observed_year"])}
    annual = fields.get("statement_period") or {}
    if annual.get("observed_value") != "annual_statement_period":
        return {}
    try:
        end = date.fromisoformat(annual["observed_end_date"])
    except (KeyError, ValueError, TypeError):
        return {}
    if (end.month, end.day) != (12, 31) or annual.get("observed_statement_year") != end.year:
        return {}
    if kind == "relative_current":
        return {"annual_current": str(end.year)}
    if kind == "relative_previous" and end.year > 1900:
        return {"annual_previous": str(end.year - 1)}
    return {}


def bindings(view):
    """Caller must supply a linked view already verified against both OCR sources and PDF."""
    identity = {k: view[k] for k in ("ocr_run_id", "ocr_run_seal_sha256", "policy_id", "policy_sha256")}
    identity.update(header_ocr_run_id=view.get("header_ocr_run_id"), header_ocr_seal_sha256=view.get("header_ocr_seal_sha256"),
                    version_id=view["source"]["version_id"], content_hash=view["source"]["content_hash"])
    result = {}
    for page in view["pages"]:
        for cell in page["cells"]:
            candidate = cell["candidate_id"]
            if candidate in result:
                raise ValueError("Duplicate OCR candidate identity")
            fields = cell["fields"]
            missing = [name for name in ("label", "value", "period", "unit", "statement_scope") if not fields.get(name)]
            options = year_options(cell)
            if not options:
                missing.append("supported_year_basis")
            if fields["value"]["text"] == "-":
                missing.append("numeric_value_not_dash")
            source = {"view": identity, "candidate_id": candidate, "page": page["page"], "column_id": cell["column_id"],
                      "fields": fields, "label_parts": cell.get("label_parts", []), "review_reasons": cell["review_reasons"]}
            result[candidate] = {"source": source, "binding_sha256": sha256(canonical(source)),
                                 "requirements": {"can_confirm": not missing, "missing": missing,
                                                  "year_methods": list(options), "all_checks_required": True}}
    return result


def validate_review(review, binding):
    if review.status != "pending" and not review.declaration:
        raise ValueError("Declare that you checked this source on the PDF")
    if review.status != "confirmed":
        if review.interpretation is not None or review.year_method or review.calendar_mapping_checked:
            raise ValueError("Only confirmed reviews contain an interpretation or year mapping")
        if review.status != "pending" and not review.notes.strip():
            raise ValueError("Enter a reason for rejection or missing context")
        return
    if (not binding["requirements"]["can_confirm"] or not all(review.checks.model_dump().values()) or
            review.interpretation is None):
        raise ValueError("Confirmation requires complete source fields, a supported year basis and all five checks")
    fields = binding["source"]["fields"]
    options = year_options({"fields": fields})
    interpretation = review.interpretation
    if review.year_method not in options or interpretation.year != options[review.year_method]:
        raise ValueError("Reviewed year must match the selected source-backed year method")
    if review.year_method != "explicit_column" and (not review.calendar_mapping_checked or not review.year_basis_note.strip()):
        raise ValueError("Relative-year confirmation requires an explicit calendar-mapping check and explanation")
    if (interpretation.unit != fields["unit"]["observed_value"] or
            interpretation.statement_scope != fields["statement_scope"]["observed_value"]):
        raise ValueError("Reviewed unit and scope must match source locators; otherwise request more context")
    if not NUMBER.fullmatch(interpretation.value_literal) or interpretation.value_literal == "-":
        raise ValueError("Confirm a literal number without repairing/normalizing punctuation automatically")
    changed = interpretation.metric != fields["label"]["text"] or interpretation.value_literal != fields["value"]["text"]
    if changed and not review.correction_notes.strip():
        raise ValueError("Explain any manual correction to the OCR label or numeric literal")


def database_path(root, *, create=False):
    root = root.resolve()
    base = root / "outputs/ocr-reviews"
    path = base / "reviews.sqlite3"
    if (base.parent.is_symlink() or base.parent.resolve() != root / "outputs" or base.is_symlink() or
            base.resolve() != base or path.is_symlink() or (path.exists() and path.resolve().parent != base)):
        raise ValueError("OCR review database must stay in project outputs")
    if create:
        base.mkdir(parents=True, exist_ok=True)
    return path


def channel(view):
    return view["ocr_run_id"], view["policy_id"], view.get("header_ocr_run_id") or ""


def checked_events(connection, view, bound):
    rows = connection.execute("SELECT candidate_id,revision,payload FROM events "
                              "WHERE run_id=? AND policy_id=? AND header_run_id=? ORDER BY sequence", channel(view)).fetchall()
    latest, events = {}, []
    for candidate_id, revision, payload in rows:
        event = json.loads(payload)
        review = OcrReviewInput.model_validate({k: event[k] for k in OcrReviewInput.model_fields})
        if (candidate_id not in bound or review.candidate_id != candidate_id or
                (review.run_id, review.policy_id, review.header_run_id or "") != channel(view) or
                review.binding_sha256 != bound[candidate_id]["binding_sha256"] or
                event["source_binding"] != bound[candidate_id]["source"] or sha256(canonical(event)) != revision or
                event["protocol"] != PROTOCOL or event["origin"] != "local_reviewer_declaration" or
                event["independent_semantic_validation"] is not False or event["historical_availability_validated"] is not False or
                event["eligible_for_answer_context"] is not False):
            raise ValueError("OCR review checksum or source binding differs")
        if review.previous_revision != (latest[candidate_id]["revision"] if candidate_id in latest else None):
            raise ValueError("OCR review revision chain differs")
        validate_review(review, bound[candidate_id])
        event["revision"] = revision
        latest[candidate_id] = event
        events.append(event)
    return latest, events


def state(root, view):
    bound = bindings(view)
    path = database_path(root)
    latest, events = {}, []
    if path.exists():
        with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)) as connection:
            latest, events = checked_events(connection, view, bound)
    return {"protocol": PROTOCOL, "run_id": view["ocr_run_id"], "policy_id": view["policy_id"],
            "header_run_id": view.get("header_ocr_run_id"),
            "cells": [{"candidate_id": key, "binding_sha256": value["binding_sha256"], "requirements": value["requirements"],
                       "latest": latest.get(key), "history": [e for e in events if e["candidate_id"] == key]} for key, value in bound.items()],
            "revision_count": len(events), "declared_confirmed_cells": sum(e["status"] == "confirmed" for e in latest.values()),
            "independent_gold": False, "semantic_accuracy": None, "historical_availability_validated": False,
            "eligible_for_answer_context": False}


def save(root, view, review):
    bound = bindings(view)
    if (review.run_id, review.policy_id, review.header_run_id or "") != channel(view) or review.candidate_id not in bound:
        raise ValueError("Unknown OCR review source or candidate")
    binding = bound[review.candidate_id]
    if review.binding_sha256 != binding["binding_sha256"]:
        raise ReviewConflict("OCR source binding changed; reload before saving")
    validate_review(review, binding)
    if review.previous_revision is not None and not database_path(root).exists():
        raise ReviewConflict("No earlier OCR review exists; reload before saving")
    path = database_path(root, create=True)
    with closing(sqlite3.connect(path, timeout=10, isolation_level=None)) as connection:
        connection.execute("CREATE TABLE IF NOT EXISTS events (sequence INTEGER PRIMARY KEY AUTOINCREMENT, "
                           "run_id TEXT NOT NULL, policy_id TEXT NOT NULL, header_run_id TEXT NOT NULL, "
                           "candidate_id TEXT NOT NULL, revision TEXT NOT NULL UNIQUE, payload TEXT NOT NULL)")
        connection.execute("BEGIN IMMEDIATE")
        latest, _ = checked_events(connection, view, bound)
        previous = latest.get(review.candidate_id)
        if review.previous_revision != (previous["revision"] if previous else None):
            raise ReviewConflict("A newer OCR review exists; reload before saving")
        event = {**review.model_dump(), "protocol": PROTOCOL, "recorded_at": datetime.now(UTC).isoformat(),
                 "origin": "local_reviewer_declaration", "source_binding": binding["source"],
                 "independent_semantic_validation": False, "historical_availability_validated": False,
                 "eligible_for_answer_context": False}
        payload = canonical(event)
        connection.execute("INSERT INTO events (run_id,policy_id,header_run_id,candidate_id,revision,payload) VALUES (?,?,?,?,?,?)",
                           (*channel(view), review.candidate_id, sha256(payload), payload.decode("utf-8")))
        connection.commit()
    return state(root, view)
