"""Versioned evidence contracts. Acquisition time is never historical availability."""

import hashlib
import re
from datetime import UTC, date, datetime, time, timedelta
from typing import Literal
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def aware(value: datetime, field: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field} needs an explicit timezone")
    return value.astimezone(UTC)


def date_upper_bound(publication_date: date, timezone: str = "Asia/Ho_Chi_Minh") -> datetime:
    """Sensitivity-policy bound, explicitly not the actual publication instant."""
    return datetime.combine(publication_date + timedelta(days=1), time(), ZoneInfo(timezone))


def version_id_for(record_id: str, content_hash: str) -> str:
    return hashlib.sha256(f"{record_id}\0{content_hash}".encode()).hexdigest()


class EvidenceVersion(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    record_id: str = Field(min_length=1)
    version_id: str = Field(min_length=1)
    source_id: str = Field(min_length=1)
    source_url: str
    listing_url: str | None = None
    ticker: str = Field(pattern=r"^[A-Z0-9]{2,12}$")
    document_type: str = Field(min_length=1)
    title: str = Field(min_length=1)
    media_type: Literal["application/pdf", "text/html"] = "application/pdf"
    publisher: str | None = None
    author: str | None = None
    evidence_scope: Literal["issuer", "market"] = "issuer"
    related_tickers: tuple[str, ...] = ()
    entity_linking_basis: str | None = None
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    raw_snapshot_path: str
    event_at: date | datetime | None = None
    page_or_section: str | None = None
    adjustment_status: Literal[
        "not_applicable", "unknown", "verified_adjusted", "verified_unadjusted"
    ] = "not_applicable"
    retrieved_at: datetime
    system_recorded_at: datetime
    available_at: datetime | None = None
    published_at: datetime | None = None
    publication_date: date | None = None
    availability_basis: Literal[
        "unverified", "verified_publication", "conservative_date_bound"
    ] = "unverified"
    timestamp_precision: Literal["second", "minute", "day", "unknown"] = "unknown"
    timestamp_evidence_hash: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    version_basis: Literal["observation_only", "archived_bytes", "official_hash_version"] = (
        "observation_only"
    )
    version_evidence_hash: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    proof_reviewed_by: str | None = None
    proof_review_note: str | None = None
    listing_snapshot_hash: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    supersedes_version_id: str | None = None
    statement_scope: Literal["consolidated", "parent", "not_applicable", "unknown"] = "unknown"
    reporting_period: str | None = None
    currency: str | None = None
    unit: str | None = None
    rights_url: str | None = None
    rights_note: str = "Rights/redistribution not established; local research inspection only."
    data_kind: Literal["real_document", "test_fixture"] = "real_document"

    @model_validator(mode="before")
    @classmethod
    def derive_snapshot_locator(cls, value):
        if isinstance(value, dict) and isinstance(value.get("content_hash"), str):
            value = dict(value)
            digest = value["content_hash"]
            value.setdefault("raw_snapshot_path", f"blobs/{digest[:2]}/{digest}")
        return value

    @field_validator("retrieved_at", "system_recorded_at", "available_at", "published_at",
                     mode="before")
    @classmethod
    def explicit_timestamp_input(cls, value):
        if value is not None:
            if not isinstance(value, (str, datetime)):
                raise ValueError("Use explicit timezone timestamps, not epoch numbers")
            if isinstance(value, str) and re.search(r"\.\d{7,}", value):
                raise ValueError("Evidence timestamps support at most microsecond precision")
        return value

    @field_validator("event_at", mode="before")
    @classmethod
    def event_date_or_aware_time(cls, value):
        if value is None or type(value) is date:
            return value
        if isinstance(value, datetime):
            return aware(value, "event_at")
        if isinstance(value, str):
            if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
                return date.fromisoformat(value)
            return aware(datetime.fromisoformat(value.replace("Z", "+00:00")), "event_at")
        raise ValueError("event_at must be a date or explicit timezone timestamp")

    @field_validator("record_id", "version_id", "source_id", "document_type", "title")
    @classmethod
    def clean_identifier(cls, value: str) -> str:
        if value != value.strip() or not value.strip():
            raise ValueError("Identifiers and titles must be nonempty and trimmed")
        return value

    @field_validator("related_tickers")
    @classmethod
    def clean_related_tickers(cls, value):
        if len(value) != len(set(value)) or any(not re.fullmatch(r"[A-Z0-9]{2,12}", t) for t in value):
            raise ValueError("Related tickers must be unique ticker identifiers")
        return value

    @field_validator("source_url", "listing_url", "rights_url")
    @classmethod
    def source_is_public_url(cls, value: str | None) -> str | None:
        if value is not None:
            parsed = urlsplit(value)
            if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
                raise ValueError("Source references must be HTTPS URLs without credentials")
        return value

    @field_validator("retrieved_at", "system_recorded_at", "available_at", "published_at")
    @classmethod
    def timezone_required(cls, value: datetime | None, info) -> datetime | None:
        return aware(value, info.field_name) if value is not None else None

    @model_validator(mode="after")
    def check_availability(self) -> "EvidenceVersion":
        expected_path = f"blobs/{self.content_hash[:2]}/{self.content_hash}"
        if self.raw_snapshot_path != expected_path:
            raise ValueError("raw_snapshot_path must match the content-addressed blob locator")
        if self.availability_basis == "unverified" and self.available_at is not None:
            raise ValueError("Unverified evidence cannot claim available_at")
        if self.availability_basis != "unverified" and self.available_at is None:
            raise ValueError("Availability basis requires available_at")
        if self.published_at and self.available_at and self.published_at > self.available_at:
            raise ValueError("available_at precedes published_at")
        if self.availability_basis == "verified_publication":
            if self.published_at is None or self.timestamp_precision not in {"second", "minute"}:
                raise ValueError("Verified publication needs timestamp and precision")
        if self.availability_basis == "conservative_date_bound":
            if self.publication_date is None or self.published_at is not None:
                raise ValueError("Date-only availability requires date and null published_at")
            expected = date_upper_bound(self.publication_date).astimezone(UTC)
            if self.timestamp_precision != "day" or self.available_at != expected:
                raise ValueError("Date-only bound must be next local midnight in Vietnam")
        return self

    def quarantine_reasons(self, cohort: Literal["strict", "conservative"]) -> list[str]:
        reasons = []
        if self.availability_basis == "unverified":
            reasons.append("availability_unverified")
        elif cohort == "strict" and self.availability_basis != "verified_publication":
            reasons.append("date_only_excluded_from_strict")
        if not self.timestamp_evidence_hash:
            reasons.append("timestamp_proof_missing")
        if self.version_basis == "observation_only" or not self.version_evidence_hash:
            reasons.append("historical_revision_proof_missing")
        if not self.proof_reviewed_by or not self.proof_review_note:
            reasons.append("time_and_version_proof_review_missing")
        return reasons


class EvidencePage(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    record_id: str
    version_id: str
    ticker: str
    related_tickers: tuple[str, ...] = ()
    content_hash: str
    page: int = Field(ge=1)
    text: str
    text_hash: str
    source_url: str
    retrieved_at: datetime
    extractor: str
    extraction_status: Literal["text_present", "no_text_ocr_not_performed"]
    data_kind: Literal["real_document", "test_fixture"]
