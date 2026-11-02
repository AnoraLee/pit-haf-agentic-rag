"""Development page gate using observed annual column headers, never answer/page lookups."""

import json
import re

from pit_haf.data.financial_sections import contains, load_profile, normalized, topic_for
from pit_haf.data.hub import file_sha

POLICY = "configs/table_page_policy_v0_8.json"
YEAR_COLUMN = re.compile(r"(?<![\w/])(?:31/12/)?((?:19|20)\d{2})(?![\w/])")


def load_policy(root):
    p = json.loads((root / POLICY).read_text(encoding="utf-8"))
    if (p["policy_id"] != "annual_table_pages_v0.8" or p["status"] != "development_not_frozen" or
            not p["require_requested_year_header"] or p["max_column_year_tokens"] != 8 or
            p["nearby_header_lines_before"] != 1 or p["nearby_header_lines_after"] != 3 or p["max_header_words"] != 20 or
            set(p["numeric_topics"]) != {"income", "revenue", "assets", "cash"}):
        raise ValueError("Unknown annual table page policy/budget")
    return p


def inspect_headers(text, policy):
    observed = set()
    extra = []
    rows = text.splitlines()
    for i, line in enumerate(rows):
        matches = list(YEAR_COLUMN.finditer(line))
        if not 1 <= len(matches) <= policy["max_column_year_tokens"]:
            continue
        remainder = normalized(YEAR_COLUMN.sub(" ", line))
        if (len(remainder.split()) > policy["max_header_words"] or
                any(word not in policy["column_remainder_words"] for word in remainder.split())):
            continue
        nearby = normalized(" ".join(rows[max(0, i - policy["nearby_header_lines_before"]):
                                          i + policy["nearby_header_lines_after"] + 1]))
        if not any(contains(nearby, unit) for unit in policy["unit_phrases"]):
            continue
        years = sorted({m.group(1) for m in matches})
        observed.update(years)
        extra.append({"line_index": i, "text": line, "years": years})
    return {"years": sorted(observed), "column_headers": extra}


def page_check(page, expected_year, topic, policy):
    result = inspect_headers(page.text, policy)
    applies = topic in policy["numeric_topics"] and bool(expected_year)
    eligible = not applies or expected_year in result["years"]
    return {**result, "eligible": eligible,
            "reason": ("requested_year_in_observed_header" if eligible and applies else
                       "not_a_numeric_annual_query" if not applies else
                       "missing_year_header" if not result["years"] else "header_period_mismatch")}


def gate(root):
    policy = load_policy(root)
    return lambda page, year, topic: page_check(page, year, topic, policy)


def verify_selected(root, pages, *, question, year, trace):
    from pit_haf.data.evidence import EvidencePage

    policy = load_policy(root)
    expected = {"policy_id": policy["policy_id"], "policy_sha256": file_sha(root / POLICY)}
    if trace.get("annual_page_policy") != expected:
        raise ValueError("Annual table page policy identity/hash mismatch")
    topic = topic_for(question, load_profile(root))
    for item in pages:
        if not page_check(EvidencePage.model_validate(item), year, topic, policy)["eligible"]:
            raise ValueError("Selected PDF text violates the annual table page gate")
