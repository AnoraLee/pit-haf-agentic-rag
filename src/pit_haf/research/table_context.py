"""Versioned, generic relevance and conservative grouping for unreviewed PDF cells."""

import json
from collections import defaultdict

from pit_haf.data.financial_sections import contains, normalized
from pit_haf.data.snapshots import canonical
from pit_haf.llm.ollama import sha256

POLICY = "configs/table_context_v0_6.json"


def load_policy(root):
    policy = json.loads((root / POLICY).read_text(encoding="utf-8"))
    if policy["policy_id"] != "financial_cell_context_v0.6" or policy["status"] != "development_not_frozen":
        raise ValueError("Unknown/unfrozen table context policy required")
    return policy


def any_phrase(text, phrases):
    return any(contains(text, p) for p in phrases)


def income_kind(label, policy):
    for kind, rules in policy["income_intents"].items():
        if any_phrase(label, rules["labels"]):
            return kind
    if label in {normalized(x) for x in policy["net_profit_exact_label_aliases"]}:
        return "after_tax_alias"
    return "other_profit"


def relevance(query, label, policy):
    q, text = normalized(query), normalized(label)
    if any_phrase(q, policy["unsupported_queries"]):
        return False, "unsupported_query", None
    domains = [name for name, rules in policy["domains"].items() if any_phrase(q, rules["query"])]
    if not domains:
        return False, "unsupported_query", None
    if (("/" in label and any_phrase(text, policy["ratio_denominators"])) or
            any_phrase(text, policy["excluded_labels"])):
        return False, "ratio_plan_or_excluded_label", None
    for domain in domains:
        rules = policy["domains"][domain]
        if not any_phrase(text, rules["labels"]) or any_phrase(text, rules.get("exclude", [])):
            continue
        if domain != "income":
            return True, "full_domain_phrase", domain
        kind = income_kind(text, policy)
        intents = [name for name, r in policy["income_intents"].items() if any_phrase(q, r["query"])]
        # A qualified question such as EBITDA/parent profit must not fall back to plain profit.
        for specific in ("parent", "ebitda", "ebit", "operating", "gross"):
            if specific in intents:
                intents = [specific]
                break
        if intents and kind not in intents and not (kind == "after_tax_alias" and "after_tax" in intents):
            continue
        return True, "income_subtype" if intents else "full_domain_phrase", kind
    return False, "label_not_relevant_to_question", None


def build_context(bundles, *, query, year, policy, max_cells=18, max_characters=9000):
    q = normalized(query)
    domains = [name for name, rules in policy["domains"].items() if any_phrase(q, rules["query"])]
    trace = {"policy_id": policy["policy_id"], "input_year_cells": 0, "excluded": [],
             "duplicate_groups": [], "conflict_groups": [], "budget_excluded": [],
             "semantic_support": "not_assessed", "human_reviewed_facts": 0,
             "query_domains": domains,
             "query_supported": bool(domains) and not any_phrase(q, policy["unsupported_queries"])}
    rows = []
    for bundle in bundles:
        source = bundle["source"]
        for cell in bundle["table"]["cells"]:
            if cell["year"] != year:
                continue
            trace["input_year_cells"] += 1
            candidate_id = sha256(canonical({"version_id": source["version_id"], "cell_id": cell["cell_id"]}))
            f = cell["fields"]
            keep, reason, kind = relevance(query, f["label"]["text"], policy)
            if not keep or len(f["label"]["text"]) > 250:
                trace["excluded"].append({"candidate_id": candidate_id, "label": f["label"]["text"],
                                          "reason": reason if not keep else "label_too_long"})
                continue
            scope = f["statement_scope"]["value"] if f["statement_scope"] else None
            unit = f["unit"]["value"] if f["unit"] else None
            row = {"candidate_id": candidate_id, "cell_id": cell["cell_id"], "version_id": source["version_id"],
                   "page": cell["page"], "label": f["label"]["text"], "value": f["value"]["text"],
                   "year": cell["year"], "unit": f["unit"]["source"]["text"] if f["unit"] else None,
                   "observed_statement_scope": scope, "review_reasons": list(cell["review_reasons"]),
                   "human_reviewed": False, "relevance_kind": kind}
            if kind == "after_tax_alias":
                row["review_reasons"].append("net_profit_label_alias_requires_review")
            # Do not group across versions, labels, unit scales, unknown scopes or companies.
            logical = (source["version_id"], source["ticker"], normalized(row["label"]), year, unit, scope)
            if unit is None or scope is None:
                logical += (candidate_id,)
            rows.append((logical, row))
    grouped = defaultdict(list)
    for logical, row in rows:
        if not any(r["candidate_id"] == row["candidate_id"] for r in grouped[logical]):
            grouped[logical].append(row)
    merged = []
    for logical, group in grouped.items():
        by_value = defaultdict(list)
        for row in group:
            by_value[row["value"]].append(row)
        conflict = len(by_value) > 1
        group_id = sha256(canonical({"logical_key": logical}))
        if conflict:
            trace["conflict_groups"].append({"group_id": group_id, "candidate_ids": [r["candidate_id"] for r in group],
                                             "values": sorted(by_value)})
        for variants in by_value.values():
            variants.sort(key=lambda r: (len(r["review_reasons"]), r["page"], r["candidate_id"]))
            primary = dict(variants[0])
            primary["equivalent_candidates"] = [{k: r[k] for k in ("candidate_id", "cell_id", "version_id", "page")}
                                                  for r in variants]
            primary["equivalent_count"] = len(variants)
            if len(variants) > 1:
                trace["duplicate_groups"].append({"representative": primary["candidate_id"],
                                                  "candidate_ids": [r["candidate_id"] for r in variants]})
            if conflict:
                primary["conflict_group_id"] = group_id
                primary["review_reasons"] = [*primary["review_reasons"], "conflicting_values_same_label_requires_review"]
            merged.append(primary)
    # Rank full financial-label matches, not incidental words from the question boilerplate.
    priorities = {"before_tax": 5, "after_tax": 5, "after_tax_alias": 4, "parent": 4, "operating": 3}
    merged.sort(key=lambda r: (-priorities.get(r["relevance_kind"], 1), r["candidate_id"]))
    context = []
    for row in merged:
        if len(context) == max_cells or len(json.dumps([*context, row], ensure_ascii=False)) > max_characters:
            trace["budget_excluded"].append(row["candidate_id"])
        else:
            context.append(row)
    trace.update(relevant_year_cells=len(rows), context_cells=len(context),
                 grouped_duplicate_cells=sum(len(g["candidate_ids"]) - 1 for g in trace["duplicate_groups"]))
    return context, trace
