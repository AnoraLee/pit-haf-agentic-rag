"""Source-bound examples of rights notices, separate from executable corporate actions."""

import hashlib
import re
from datetime import datetime
from decimal import Decimal
from io import BytesIO
from typing import Literal

from pydantic import Field, model_validator
from pypdf import PdfReader

from pit_haf.backtest.contracts import Amount, Contract
from pit_haf.backtest.engine import literal
from pit_haf.data.session_calendar import Source, day, notice_text, validate_sources

PROTOCOL = "corporate_action_development_v0.1"


class Proof(Contract):
    field: Literal[
        "symbol",
        "record_date",
        "cash_per_share",
        "cash_payment_date",
        "stock_ratio",
        "stock_tradable_date",
        "tradable_record_date",
    ]
    source_id: str
    start: int = Field(ge=0)
    token: str = Field(min_length=1, max_length=40)


class Event(Contract):
    id: str = Field(pattern=r"^[a-z][a-z0-9_]{1,60}$")
    symbol: str = Field(pattern=r"^[A-Z][A-Z0-9]{2}$")
    record_date: str
    ex_date: None
    cash_per_share: Amount
    cash_payment_date: str | None
    ratio_old: int = Field(ge=1, le=10**6)
    ratio_new: int = Field(ge=1, le=10**6)
    stock_tradable_date: str
    proofs: list[Proof] = Field(min_length=4, max_length=12)

    @model_validator(mode="after")
    def timeline(self):
        record = day(self.record_date)
        if day(self.stock_tradable_date) < record:
            raise ValueError("New stock trading date precedes record date")
        cash = Decimal(self.cash_per_share) > 0
        if cash != (self.cash_payment_date is not None):
            raise ValueError("Cash payment date must match the cash distribution")
        if self.cash_payment_date is not None and day(self.cash_payment_date) < record:
            raise ValueError("Cash payment precedes record date")
        needed = {
            "symbol",
            "record_date",
            "stock_ratio",
            "stock_tradable_date",
            "tradable_record_date",
        }
        if cash:
            needed |= {"cash_payment_date", "cash_per_share"}
        if {p.field for p in self.proofs} != needed:
            raise ValueError("Event evidence fields differ from the observed distribution")
        return self


class Book(Contract):
    protocol: Literal["corporate_action_development_v0.1"]
    coverage: Literal["selected_examples_only_not_complete_history"]
    audit_start: str
    audit_end: str
    sources: list[Source] = Field(min_length=1, max_length=12)
    events: list[Event] = Field(min_length=1, max_length=20)
    disagreements: list["Disagreement"] = Field(default_factory=list, max_length=20)

    @model_validator(mode="after")
    def identity(self):
        if day(self.audit_start) >= day(self.audit_end):
            raise ValueError("Corporate audit requires an ordered date window")
        source_ids = {s.id for s in self.sources}
        if len(source_ids) != len(self.sources) or len({e.id for e in self.events}) != len(
            self.events
        ):
            raise ValueError("Duplicate corporate source or event")
        if len({(e.symbol, e.record_date) for e in self.events}) != len(self.events):
            raise ValueError("Combine distributions for a single symbol/record date")
        used = set()
        for event in self.events:
            if (
                not self.audit_start <= event.record_date <= self.audit_end
                or event.stock_tradable_date > self.audit_end
                or (
                    event.cash_payment_date is not None and event.cash_payment_date > self.audit_end
                )
            ):
                raise ValueError("Observed action dates must stay inside the audit window")
            ids = {p.source_id for p in event.proofs}
            if not ids <= source_ids or ids != {
                p.source_id for p in event.proofs if p.field == "symbol"
            }:
                raise ValueError("Each used source must identify the same equity symbol")
            used |= ids
        if used != source_ids:
            raise ValueError("Unused source in corporate book")
        event_map = {e.id: e for e in self.events}
        if len({d.event_id for d in self.disagreements}) != len(self.disagreements):
            raise ValueError("Duplicate event disagreement")
        for item in self.disagreements:
            if (
                item.event_id not in event_map
                or item.issuer_symbol != event_map[item.event_id].symbol
                or day(item.other_record_date).isoformat() == event_map[item.event_id].record_date
            ):
                raise ValueError("Disagreement must name an event and a different record date")
        return self


class Disagreement(Contract):
    event_id: str
    issuer_symbol: str = Field(pattern=r"^[A-Z][A-Z0-9]{2}$")
    other_record_date: str
    source_url: str = Field(pattern=r"^https://file\.hoaphat\.com\.vn/[^\s]+\.pdf$")
    content_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    pdf_page: int = Field(ge=1, le=3000)
    basis: Literal["assistant_visual_read_of_original_pdf_page"]
    independent_confirmation: Literal[False]


def parse_token(field, token):
    if field == "symbol":
        if not re.fullmatch(r"[A-Z][A-Z0-9]{2}", token):
            raise ValueError("Invalid corporate symbol token")
        return token
    if field in {"record_date", "cash_payment_date", "stock_tradable_date", "tradable_record_date"}:
        if not re.fullmatch(r"\d{1,2}/\d{1,2}/\d{4}", token):
            raise ValueError("Require explicit dd/mm/yyyy source date")
        return datetime.strptime(token, "%d/%m/%Y").date().isoformat()
    if field == "cash_per_share":
        if not re.fullmatch(r"(?:[1-9]\d{0,2}(?:\.\d{3})+|0|[1-9]\d*)", token):
            raise ValueError("Require unambiguous integer cash per share token")
        return str(int(token.replace(".", "")))
    match = re.fullmatch(r"\s*(\d{1,6}|[1-9]\d{0,2}(?:\.\d{3})+)\s*:\s*(\d{1,6})\s*", token)
    if not match:
        raise ValueError("Require old:new shares ratio, never percent of face value")
    return int(match[1].replace(".", "")), int(match[2])


def audit(book, payloads, normalized, *, external_pdfs=None):
    book = Book.model_validate(book.model_dump())
    source_observations = validate_sources(book, payloads)
    bodies = {key: notice_text(value) for key, value in payloads.items()}
    external_pdfs = external_pdfs or {}
    if set(external_pdfs) != {d.content_hash for d in book.disagreements}:
        raise ValueError("Corporate PDF dependency set differs")
    for item in book.disagreements:
        raw = external_pdfs[item.content_hash]
        if (
            len(raw) > 32 * 1024 * 1024
            or hashlib.sha256(raw).hexdigest() != item.content_hash
            or item.pdf_page > len(PdfReader(BytesIO(raw)).pages)
        ):
            raise ValueError("Corporate PDF bytes or page differ")
    if len({n["symbol"] for n in normalized}) != len(normalized):
        raise ValueError("Duplicate price symbol in corporate audit")
    prices = {n["symbol"]: n["normalized"] for n in normalized}
    rows = []
    conflicts = {d.event_id: d for d in book.disagreements}
    for event in book.events:
        expected = {
            "symbol": event.symbol,
            "record_date": event.record_date,
            "tradable_record_date": event.record_date,
            "stock_tradable_date": event.stock_tradable_date,
            "cash_per_share": literal(Decimal(event.cash_per_share)),
            "cash_payment_date": event.cash_payment_date,
            "stock_ratio": (event.ratio_old, event.ratio_new),
        }
        for proof in event.proofs:
            body = bodies[proof.source_id]
            if (
                body[proof.start : proof.start + len(proof.token)] != proof.token
                or parse_token(proof.field, proof.token) != expected[proof.field]
            ):
                raise ValueError("Corporate evidence locator or observed field differs")
        n = prices.get(event.symbol)
        sessions = {b["session_date"] for b in n["bars"]} if n else set()
        adjustment = n["adjustment_status"] if n else "unavailable"
        row = {
            "id": event.id,
            "symbol": event.symbol,
            "record_date": event.record_date,
            "ex_date": None,
            "cash_per_share": event.cash_per_share,
            "cash_basis": "reported_cash_distribution"
            if Decimal(event.cash_per_share) > 0
            else "not_reported_in_selected_notice",
            "cash_payment_date": event.cash_payment_date,
            "ratio_old": event.ratio_old,
            "ratio_new": event.ratio_new,
            "stock_tradable_date": event.stock_tradable_date,
            "calendar_days_record_to_stock_trading": (
                day(event.stock_tradable_date) - day(event.record_date)
            ).days,
            "record_date_in_price_snapshot": event.record_date in sessions,
            "stock_trading_date_in_price_snapshot": event.stock_tradable_date in sessions,
            "snapshot_adjustment_status": adjustment,
            "availability_at": None,
            "entitlement_quantity": None,
            "blocking_reasons": [
                "ex_date_not_sourced",
                "broker_credit_time_unknown",
                "complete_corporate_action_history_not_established",
                "adjustment_factor_lineage_not_verified",
                "holder_quantity_not_established",
            ],
        }
        disagreement = conflicts.get(event.id)
        row["record_date_status"] = (
            "unresolved_disagreement" if disagreement else "observed_in_selected_notices_only"
        )
        if disagreement:
            row["blocking_reasons"].append("record_date_disagrees_with_issuer_report")
        rows.append(row)
    return {
        "protocol": PROTOCOL,
        "kind": "real_corporate_action_source_diagnostic",
        "coverage": book.coverage,
        "source_observations": source_observations,
        "events": rows,
        "notice_tokens_match": True,
        "cross_source_disagreements": [
            d.model_dump()
            | {"notice_record_date": next(e.record_date for e in book.events if e.id == d.event_id)}
            for d in book.disagreements
        ],
        "eligible_for_execution": False,
        "research_result": False,
        "historical_availability_validated": False,
        "independent_gold": False,
        "automatic_price_adjustments": 0,
        "orders_generated": 0,
    }
