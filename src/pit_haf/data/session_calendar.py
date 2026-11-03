"""Retrospective settlement-date candidates from explicitly curated notice revisions."""

import hashlib
import re
from datetime import date, timedelta
from typing import Literal

from bs4 import BeautifulSoup
from pydantic import Field, model_validator

from pit_haf.backtest.contracts import Contract

PROTOCOL = "settlement_calendar_audit_v0.1"


def day(value):
    if not isinstance(value, str):
        raise ValueError("Calendar date must be an ISO date string")
    result = date.fromisoformat(value)
    if result.isoformat() != value:
        raise ValueError("Calendar date must be canonical YYYY-MM-DD")
    return result


def dates(start, end):
    first, last = day(start), day(end)
    if not 0 <= (last - first).days <= 1470:
        raise ValueError("Calendar range must be ordered and bounded to 1471 days")
    return [(first + timedelta(days=i)).isoformat() for i in range((last - first).days + 1)]


def notice_text(raw):
    if len(raw) > 8 * 1024 * 1024:
        raise ValueError("Calendar notice exceeds 8 MiB")
    soup = BeautifulSoup(raw.decode("utf-8-sig"), "html.parser")
    body = soup.select_one(".content-category")
    if body is None:
        raise ValueError("Missing VSDC notice body")
    return " ".join(body.get_text(" ", strip=True).split())


class Source(Contract):
    id: str = Field(pattern=r"^[a-z][a-z0-9_]{1,60}$")
    url: str = Field(pattern=r"^https://vsdc\.vn/vi/ad/[0-9]+$")
    raw_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    body_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    anchors: list[str] = Field(min_length=1, max_length=20)


class Closure(Contract):
    start: str
    end: str
    source_id: str
    reason: Literal[
        "new_year",
        "lunar_new_year",
        "hung_kings",
        "april_may",
        "national_day",
        "no_equity_settlement_on_makeup_day",
    ]

    @model_validator(mode="after")
    def ordered(self):
        dates(self.start, self.end)
        return self


class Revision(Contract):
    id: str = Field(pattern=r"^[a-z][a-z0-9_]{1,60}$")
    start: str
    end: str
    supersedes: str | None
    closures: list[Closure] = Field(min_length=1, max_length=20)

    @model_validator(mode="after")
    def window(self):
        dates(self.start, self.end)
        if day(self.start).year != day(self.end).year:
            raise ValueError("Each revision covers one year or an explicit within-year tail")
        seen = set()
        for closure in self.closures:
            if not self.start <= closure.start <= closure.end <= self.end:
                raise ValueError("Closure outside revision window")
            span = set(dates(closure.start, closure.end))
            if seen & span:
                raise ValueError("Overlapping closures within a revision")
            seen |= span
        return self


class Profile(Contract):
    protocol: Literal["settlement_calendar_audit_v0.1"]
    basis: Literal["candidate_weekdays_minus_curated_VSDC_closures"]
    scope: Literal["cash_equity_settlement_dates_only"]
    audit_start: str
    audit_end: str
    sources: list[Source] = Field(min_length=1, max_length=12)
    revisions: list[Revision] = Field(min_length=1, max_length=15)
    selected: list[str] = Field(min_length=1, max_length=5)

    @model_validator(mode="after")
    def lineage(self):
        dates(self.audit_start, self.audit_end)
        sources = {s.id for s in self.sources}
        if len(sources) != len(self.sources):
            raise ValueError("Duplicate calendar source")
        known, roots, children = {}, set(), set()
        for revision in self.revisions:
            if revision.id in known or any(c.source_id not in sources for c in revision.closures):
                raise ValueError("Duplicate revision or unknown closure source")
            window = (revision.start, revision.end)
            if revision.supersedes is not None:
                prior = known.get(revision.supersedes)
                if prior is None or (prior.start, prior.end) != window or prior.id in children:
                    raise ValueError("Revision must replace a prior identical window without forks")
                children.add(prior.id)
            elif window in roots:
                raise ValueError("Ambiguous root calendar revision")
            else:
                roots.add(window)
            known[revision.id] = revision
        leaves = set(known) - children
        if len(set(self.selected)) != len(self.selected) or set(self.selected) != leaves:
            raise ValueError("Select every final revision exactly once, never an obsolete revision")
        selected = [known[key] for key in self.selected]
        if [r.start for r in selected] != sorted(r.start for r in selected) or any(
            day(a.end) + timedelta(days=1) != day(b.start) for a, b in zip(selected, selected[1:])
        ):
            raise ValueError(
                "Selected calendar windows must be ordered, contiguous and nonoverlapping"
            )
        if not selected[0].start <= self.audit_start <= self.audit_end <= selected[-1].end:
            raise ValueError("Audit window outside supplied calendar")
        dates(selected[0].start, selected[-1].end)
        return self


def validate_sources(profile, payloads):
    if set(payloads) != {s.id for s in profile.sources}:
        raise ValueError("Calendar source payload set differs")
    observations = []
    for source in profile.sources:
        raw = payloads[source.id]
        body = notice_text(raw)
        if (
            hashlib.sha256(raw).hexdigest() != source.raw_sha256
            or hashlib.sha256(body.encode()).hexdigest() != source.body_sha256
            or any(not anchor or anchor not in body for anchor in source.anchors)
        ):
            raise ValueError("Calendar notice bytes, body or curation anchors differ")
        observations.append(
            {
                "source_id": source.id,
                "url": source.url,
                "raw_sha256": source.raw_sha256,
                "body_sha256": source.body_sha256,
                "body_characters": len(body),
                "semantic_review": "assistant_curation_not_independent_gold",
            }
        )
    return observations


def revision_days(revision):
    closed = {d: c for c in revision.closures for d in dates(c.start, c.end)}
    rows = []
    for label in dates(revision.start, revision.end):
        closure = closed.get(label)
        weekend = day(label).weekday() >= 5
        rows.append(
            {
                "date": label,
                "revision": revision.id,
                "weekday": day(label).weekday(),
                "candidate_settlement_day": not weekend and closure is None,
                "reason": closure.reason
                if closure
                else "weekend_assumption"
                if weekend
                else "weekday_candidate",
                "source_id": closure.source_id if closure else None,
                "available_at": None,
            }
        )
    return rows


def build_calendar(profile):
    profile = Profile.model_validate(profile.model_dump())
    revisions = {r.id: r for r in profile.revisions}
    rows = [row for key in profile.selected for row in revision_days(revisions[key])]
    changes = []
    for revision in profile.revisions:
        if revision.supersedes:
            prior = {r["date"]: r for r in revision_days(revisions[revision.supersedes])}
            for row in revision_days(revision):
                old = prior[row["date"]]
                if old["candidate_settlement_day"] != row["candidate_settlement_day"]:
                    changes.append(
                        {
                            "date": row["date"],
                            "prior_revision": revision.supersedes,
                            "revision": revision.id,
                            "prior_open": old["candidate_settlement_day"],
                            "revised_open": row["candidate_settlement_day"],
                        }
                    )
    return rows, changes


def reconcile(profile, calendar, observed):
    profile = Profile.model_validate(profile.model_dump())
    if calendar != build_calendar(profile)[0]:
        raise ValueError("Calendar rows differ from the selected profile")
    expected = {
        r["date"]
        for r in calendar
        if profile.audit_start <= r["date"] <= profile.audit_end and r["candidate_settlement_day"]
    }
    all_open = [r["date"] for r in calendar if r["candidate_settlement_day"]]
    if len(expected) < 2:
        raise ValueError("Audit needs at least two candidate settlement days")
    positions = {d: i for i, d in enumerate(all_open)}
    assets = []
    for symbol, values in sorted(observed.items()):
        if not re.fullmatch(r"[A-Z][A-Z0-9]{2}", symbol) or not isinstance(values, list):
            raise ValueError("Expected three-character equity symbols and date lists")
        for value in values:
            day(value)
        if len(values) != len(set(values)) or any(
            not profile.audit_start <= v <= profile.audit_end for v in values
        ):
            raise ValueError("Duplicate or out-of-window observed session dates")
        found = set(values)
        assets.append(
            {
                "symbol": symbol,
                "observed_sessions": len(values),
                "missing_candidate_dates": sorted(expected - found),
                "unexpected_observed_dates": sorted(found - expected),
                "date_set_matches_candidate": found == expected,
            }
        )
    settlement = []
    for label in sorted(expected):
        index = positions[label]
        if index + 2 >= len(all_open):
            raise ValueError("Calendar tail is insufficient for a T+2 date")
        settlement.append(
            {
                "trade_date": label,
                "candidate_T2_date": all_open[index + 2],
                "shares_available_at": None,
                "sale_cash_available_at": None,
            }
        )
    yearly = {
        str(year): sum(day(d).year == year for d in expected)
        for year in range(day(profile.audit_start).year, day(profile.audit_end).year + 1)
    }
    return {
        "protocol": PROTOCOL,
        "scope": profile.scope,
        "basis": profile.basis,
        "candidate_sessions": len(expected),
        "candidate_sessions_by_year": yearly,
        "assets": assets,
        "candidate_T2_dates": settlement,
        "date_sets_match": bool(assets) and all(a["date_set_matches_candidate"] for a in assets),
        "venue_calendar_verified": False,
        "broker_availability_verified": False,
        "historical_availability_validated": False,
        "independent_gold": False,
        "eligible_for_execution": False,
        "research_result": False,
    }
