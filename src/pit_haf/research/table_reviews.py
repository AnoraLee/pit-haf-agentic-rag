"""Revisioned local declarations for individual PDF-cell locations, separate from runs."""

import json
import sqlite3
from contextlib import closing
from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from pit_haf.data.hub import file_sha
from pit_haf.data.snapshots import canonical
from pit_haf.llm.ollama import sha256
from pit_haf.research.reviews import ReviewConflict
from pit_haf.research.table_views import run_folder

HEX = r"^[a-f0-9]{64}$"
RUN = r"^\d{8}T\d{6}Z-[a-f0-9]{8}$"
CHECKS = ("label", "value", "year", "unit", "statement_scope")


class CellChecks(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    label: bool = False
    value: bool = False
    year: bool = False
    unit: bool = False
    statement_scope: bool = False


class CellInterpretation(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    metric: str = Field(min_length=1, max_length=200)
    year: str = Field(pattern=r"^(?:19|20)\d{2}$")
    unit: str = Field(min_length=1, max_length=100)
    statement_scope: Literal["consolidated", "parent"]

    @field_validator("metric", "unit")
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError("Enter a nonblank interpretation")
        return value.strip()


class TableReviewInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    run_id: str = Field(pattern=RUN)
    candidate_id: str = Field(pattern=HEX)
    source_cell_id: str = Field(pattern=HEX)
    binding_sha256: str = Field(pattern=HEX)
    previous_revision: str | None = Field(default=None, pattern=HEX)
    status: Literal["pending", "confirmed", "rejected", "needs_context"]
    reviewer: str = Field(min_length=1, max_length=100)
    declaration: bool = False
    checks: CellChecks = Field(default_factory=CellChecks)
    interpretation: CellInterpretation | None = None
    notes: str = Field(default="", max_length=3000)

    @field_validator("reviewer")
    @classmethod
    def named_reviewer(cls, value):
        if not value.strip():
            raise ValueError("Enter a reviewer name or initials")
        return value.strip()


def bindings(root, view):
    """Bind a declaration to one raw locator, never automatically to its group siblings."""
    run_id = view["run"]["run_id"]
    integrity = file_sha(run_folder(root, run_id) / "integrity.json")
    sources = {s["index"]: s for s in view["sources"]}
    result = {}
    for cell in view["cells"]:
        for location in cell["source_alternatives"]:
            source = sources[location["source_index"]]
            identity = {"run_id": run_id, "run_integrity_sha256": integrity,
                        "candidate_id": cell["candidate_id"], "source_cell_id": location["cell_id"],
                        "version_id": source["version_id"], "content_hash": source["content_hash"],
                        "extractor": source["extractor"], "page": location["page"],
                        "fields": location["fields"], "conflict_group_id": cell.get("conflict_group_id")}
            key = (cell["candidate_id"], location["cell_id"])
            result[key] = {"binding_sha256": sha256(canonical(identity)), "source": identity}
    return result


def validate_review(review, binding):
    if review.status != "pending" and not review.declaration:
        raise ValueError("Declare that you checked this source location")
    if review.status == "confirmed":
        if not all(review.checks.model_dump().values()) or review.interpretation is None:
            raise ValueError("Confirmation requires all five checks and an interpretation")
        source = binding["source"]
        fields = source["fields"]
        if source["conflict_group_id"]:
            raise ValueError("Conflicting values need context; this group cannot be confirmed")
        if not fields["unit"] or not fields["statement_scope"]:
            raise ValueError("Missing unit/scope source locator; mark needs_context instead")
        interpretation = review.interpretation
        if (interpretation.year != fields["period"]["text"] or
                interpretation.unit != fields["unit"]["value"] or
                interpretation.statement_scope != fields["statement_scope"]["value"]):
            raise ValueError("Year/unit/scope must match this source location")
    else:
        if review.interpretation is not None:
            raise ValueError("Only confirmed reviews have an interpretation")
        if review.status != "pending" and not review.notes.strip():
            raise ValueError("Enter a reason for rejection or missing context")


def database_path(root, *, create=False):
    root = root.resolve()
    base = root / "outputs/table-reviews"
    path = base / "reviews.sqlite3"
    if (base.parent.is_symlink() or base.parent.resolve() != root / "outputs" or
            base.is_symlink() or base.resolve() != base or path.is_symlink()):
        raise ValueError("Review database must stay in the project output directory")
    if create:
        base.mkdir(parents=True, exist_ok=True)
    # Resolving a missing leaf while another writer creates it can race on Windows.
    # A normal file cannot leave the already-checked parent; reject redirected existing leaves.
    if path.is_symlink() or (path.exists() and path.resolve().parent != base):
        raise ValueError("Review database must stay in the project output directory")
    return path


def checked_events(connection, view, bound):
    rows = connection.execute("SELECT run_id,candidate_id,source_cell_id,revision,payload "
                              "FROM events WHERE run_id=? ORDER BY sequence", (view["run"]["run_id"],)).fetchall()
    latest, events = {}, []
    for run_id, candidate, cell_id, revision, payload in rows:
        event = json.loads(payload)
        key = (candidate, cell_id)
        review = TableReviewInput.model_validate({k: event[k] for k in TableReviewInput.model_fields})
        if (sha256(canonical(event)) != revision or review.run_id != run_id or
                (review.candidate_id, review.source_cell_id) != key or key not in bound or
                event["source_binding"] != bound[key]["source"] or
                review.binding_sha256 != bound[key]["binding_sha256"] or
                event["protocol"] != "table_location_reviews_v0.1" or
                event["source"] != "local_reviewer_declaration" or
                event["independent_semantic_validation"] is not False or
                event["historical_availability_validated"] is not False):
            raise ValueError("Table review checksum/source binding mismatch")
        if review.previous_revision != (latest[key]["revision"] if key in latest else None):
            raise ValueError("Table review revision chain mismatch")
        validate_review(review, bound[key])
        event["revision"] = revision
        latest[key] = event
        events.append(event)
    return latest, events


def state(root, view):
    bound = bindings(root, view)
    path = database_path(root)
    latest, events = {}, []
    if path.exists():
        with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)) as connection:
            latest, events = checked_events(connection, view, bound)
    return {"protocol": "table_location_reviews_v0.1", "run_id": view["run"]["run_id"],
            "locations": [{"candidate_id": key[0], "source_cell_id": key[1],
                           "binding_sha256": value["binding_sha256"], "latest": latest.get(key),
                           "history": [e for e in events if (e["candidate_id"], e["source_cell_id"]) == key]}
                          for key, value in bound.items()],
            "declared_confirmed_locations": sum(e["status"] == "confirmed" for e in latest.values()),
            "revision_count": len(events), "independent_gold": False, "semantic_accuracy": None,
            "historical_availability_validated": False}


def save(root, view, review):
    bound = bindings(root, view)
    key = (review.candidate_id, review.source_cell_id)
    if review.run_id != view["run"]["run_id"] or key not in bound:
        raise ValueError("Unknown table run/candidate/source location")
    if review.binding_sha256 != bound[key]["binding_sha256"]:
        raise ReviewConflict("Source binding changed; reload before saving")
    validate_review(review, bound[key])
    path = database_path(root, create=True)
    with closing(sqlite3.connect(path, timeout=10, isolation_level=None)) as connection:
        connection.execute("BEGIN IMMEDIATE")
        connection.execute("CREATE TABLE IF NOT EXISTS events (sequence INTEGER PRIMARY KEY AUTOINCREMENT, "
                           "run_id TEXT NOT NULL, candidate_id TEXT NOT NULL, source_cell_id TEXT NOT NULL, "
                           "revision TEXT NOT NULL UNIQUE, payload TEXT NOT NULL)")
        latest, _ = checked_events(connection, view, bound)
        previous = latest.get(key)
        if review.previous_revision != (previous["revision"] if previous else None):
            raise ReviewConflict("A newer review exists; reload before saving")
        event = {**review.model_dump(), "protocol": "table_location_reviews_v0.1",
                 "recorded_at": datetime.now(UTC).isoformat(), "source": "local_reviewer_declaration",
                 "source_binding": bound[key]["source"], "independent_semantic_validation": False,
                 "historical_availability_validated": False}
        payload = canonical(event)
        revision = sha256(payload)
        connection.execute("INSERT INTO events (run_id,candidate_id,source_cell_id,revision,payload) VALUES (?,?,?,?,?)",
                           (review.run_id, *key, revision, payload.decode("utf-8")))
        connection.commit()
    return state(root, view)
