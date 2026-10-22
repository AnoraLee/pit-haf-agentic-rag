"""Local annotation workbench: immutable source packs and append-only declared reviews."""

import json
import os
import re
from collections import Counter
from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from pit_haf.data.hub import file_sha
from pit_haf.llm.ollama import sha256
from pit_haf.research.reports import ReportDraft, verify_claims


class ReviewConflict(ValueError):
    pass


class ReviewInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    pack_id: str = Field(pattern=r"^\d{8}T\d{6}Z-[0-9a-f]{8}$")
    case_id: str = Field(pattern=r"^[A-Za-z0-9-]{1,100}$")
    previous_revision: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    status: str = Field(pattern=r"^(pending|answered|unanswerable|needs_ocr|wrong_period)$")
    reviewer: str = Field(min_length=1, max_length=100)
    declaration: bool
    answers: list[dict] = Field(default_factory=list, max_length=3)
    notes: str = Field(default="", max_length=3000)

    @field_validator("reviewer")
    @classmethod
    def named_reviewer(cls, value):
        if not value.strip():
            raise ValueError("Enter a reviewer name or initials")
        return value.strip()


def active_pack(root):
    paths = sorted(root.glob("data/development/*/case_index.json"), reverse=True)
    if not paths:
        raise FileNotFoundError("No development pack is published")
    index = json.loads(paths[0].read_text(encoding="utf-8"))
    pack_id = index["pack_id"]
    if not re.fullmatch(r"\d{8}T\d{6}Z-[0-9a-f]{8}", pack_id):
        raise ValueError("Invalid published pack ID")
    base = (root / "outputs/development-cases").resolve()
    folder = base / pack_id
    if folder.resolve().parent != base or folder.is_symlink():
        raise ValueError("Pack must stay in its local output directory")
    summary = json.loads((folder / "summary.json").read_text(encoding="utf-8"))
    if summary["pack_id"] != pack_id or summary["cases_sha256"] != index["cases_sha256"]:
        raise ValueError("Published index and source pack disagree")
    if file_sha(folder / "cases.jsonl") != index["cases_sha256"]:
        raise ValueError("Development case source checksum mismatch")
    rows = [json.loads(line) for line in (folder / "cases.jsonl").read_text(encoding="utf-8").splitlines()]
    cases = {row["case_id"]: row for row in rows}
    if len(cases) != len(rows) or len(cases) != index["cases"]:
        raise ValueError("Development case identity/coverage mismatch")
    return index, cases


def ledger(root, pack_id, expected_cases_sha256=None):
    path = root / "outputs/development-reviews" / pack_id / "reviews.jsonl"
    latest = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            event = json.loads(line)
            revision = event.pop("revision")
            payload = json.dumps(event, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
            if revision != sha256(payload) or event["pack_id"] != pack_id:
                raise ValueError("Review ledger checksum mismatch")
            if expected_cases_sha256 and event["cases_sha256"] != expected_cases_sha256:
                raise ValueError("Review belongs to a different source snapshot")
            previous = latest.get(event["case_id"])
            if event["previous_revision"] != (previous["revision"] if previous else None):
                raise ValueError("Review ledger revision chain mismatch")
            latest[event["case_id"]] = {**event, "revision": revision}
    return path, latest


def list_cases(root):
    index, cases = active_pack(root)
    _, reviews = ledger(root, index["pack_id"], index["cases_sha256"])
    counts = Counter(reviews.get(case_id, {}).get("status", "pending") for case_id in cases)
    return {"pack_id": index["pack_id"], "cases_sha256": index["cases_sha256"],
            "cases": [{"case_id": c["case_id"], "ticker": c["ticker"], "question": c["question"],
                       "status": reviews.get(c["case_id"], {}).get("status", "pending")} for c in cases.values()],
            "counts": dict(counts), "declared_reviewed_cases": len(cases) - counts["pending"],
            "semantic_support_independently_validated": False, "historical_availability_validated": False}


def case_detail(root, case_id):
    index, cases = active_pack(root)
    if case_id not in cases:
        raise KeyError("Unknown development case")
    _, reviews = ledger(root, index["pack_id"], index["cases_sha256"])
    return {"pack_id": index["pack_id"], "cases_sha256": index["cases_sha256"],
            "case": cases[case_id], "review": reviews.get(case_id)}


def export_reviews(root):
    index, cases = active_pack(root)
    _, latest = ledger(root, index["pack_id"], index["cases_sha256"])
    rows = [latest.get(case_id, {"case_id": case_id, "status": "pending", "reviewer": None,
                                "reviewed_at": None, "answers": [], "notes": ""}) for case_id in cases]
    return {"pack_id": index["pack_id"], "annotations": rows,
            "human_reviewed_status_is_declared_not_independently_validated": True}


def validate_answer(review, case):
    """Use the same annotation contract on write and when evaluating a saved ledger."""
    if review.status != "pending" and not review.declaration:
        raise ValueError("The reviewer must explicitly declare that the source was checked")
    if review.status == "answered":
        draft = ReportDraft(claims=review.answers, missing_information=[], insufficient_evidence=False)
        accepted, rejected = verify_claims(draft, case["evidence"], True)
        if not accepted or rejected:
            raise ValueError("Every reviewed answer needs a unique literal quote and supported numbers")
    elif review.answers or review.status != "pending" and not review.notes.strip():
        raise ValueError("Non-answer reviews need a reason and no supported answers")


def save_review(root, review):
    index, cases = active_pack(root)
    if review.pack_id != index["pack_id"]:
        raise ReviewConflict("The active pack changed; reload the case")
    if review.case_id not in cases:
        raise ValueError("Unknown development case")
    path, latest = ledger(root, review.pack_id, index["cases_sha256"])
    previous = latest.get(review.case_id)
    if review.previous_revision != (previous["revision"] if previous else None):
        raise ReviewConflict("This case has a newer review; reload before saving")
    validate_answer(review, cases[review.case_id])
    event = {**review.model_dump(), "reviewed_at": datetime.now(UTC).isoformat(),
             "cases_sha256": index["cases_sha256"], "source": "local_workbench_reviewer_declaration",
             "independent_semantic_validation": False, "historical_availability_validated": False}
    payload = json.dumps(event, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    event["revision"] = sha256(payload)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("ab") as stream:
        stream.write(json.dumps(event, ensure_ascii=False, separators=(",", ":")).encode() + b"\n")
        stream.flush()
        os.fsync(stream.fileno())
    return event
