"""Explicit document scope for report retrieval; metadata matching is not PiT proof."""

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

REPORT_KINDS = ("annual_report", "financial_statement", "financial_report", "earnings_overview", "business_overview")


class ReportScope(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    ticker: str = Field(pattern=r"^[A-Z0-9]{2,12}$")
    reporting_period: str | None = Field(default=None, pattern=r"^(?:19|20)\d{2}(?:-Q[1-4])?$")
    source_policy: Literal["issuer_reports", "all_linked"] = "issuer_reports"
    statement_scope: Literal["all", "consolidated", "parent"] = "all"
    period_basis: Literal["explicit", "question", "unrestricted", "ambiguous_question"] = "unrestricted"

    def sql(self):
        clauses, params = ["1=1"], []
        if self.source_policy == "issuer_reports":
            clauses.extend(["d.ticker=?", "json_extract(d.metadata_json,'$.media_type')='application/pdf'",
                            "d.kind IN (" + ",".join("?" for _ in REPORT_KINDS) + ")"])
            params.extend([self.ticker, *REPORT_KINDS])
        else:
            clauses.append("EXISTS(SELECT 1 FROM links l WHERE l.version_id=d.version_id AND l.ticker=?)")
            params.append(self.ticker)
        if self.reporting_period:
            # News metadata carries publication year, not a verified accounting period.
            clauses.extend(["json_extract(d.metadata_json,'$.media_type')='application/pdf'",
                            "json_extract(d.metadata_json,'$.reporting_period')=?"])
            params.append(self.reporting_period)
        if self.statement_scope != "all":
            clauses.append("d.scope=?")
            params.append(self.statement_scope)
        return " AND ".join(clauses), params

    def matches(self, version):
        if self.source_policy == "issuer_reports":
            if (version.ticker != self.ticker or version.media_type != "application/pdf" or
                    version.document_type not in REPORT_KINDS):
                return False
        elif version.ticker != self.ticker and self.ticker not in version.related_tickers:
            return False
        if self.reporting_period and (version.media_type != "application/pdf" or version.reporting_period != self.reporting_period):
            return False
        return self.statement_scope == "all" or version.statement_scope == self.statement_scope


def resolve_scope(query, ticker, *, reporting_period=None, source_policy="issuer_reports", statement_scope="all"):
    period, basis = reporting_period, "explicit"
    if reporting_period == "all":
        period, basis = None, "unrestricted"
    elif reporting_period is None:
        years = sorted(set(re.findall(r"\b(?:19|20)\d{2}\b", query)))
        period = years[0] if len(years) == 1 else None
        basis = "question" if period else "ambiguous_question" if years else "unrestricted"
        quarters = re.findall(r"(?:quý\s*|\bQ)(IV|III|II|I|[1-4])\b", query, flags=re.IGNORECASE)
        if period and quarters:
            values = {str({"I": 1, "II": 2, "III": 3, "IV": 4}.get(q.upper(), q)) for q in quarters}
            if len(values) == 1:
                period += "-Q" + values.pop()
            else:
                period, basis = None, "ambiguous_question"
    return ReportScope(ticker=ticker, reporting_period=period, source_policy=source_policy,
                       statement_scope=statement_scope, period_basis=basis)
