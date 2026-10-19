"""Decimal calculations on reviewed, compatible facts; never guess units from model prose."""

from decimal import Decimal, InvalidOperation


def calculate(kind, left, right):
    """Inputs carry reviewed values and evidence IDs; upstream must check their locators.

    This development calculator does not promote a model-extracted quantity to a
    reviewed fact. No company calculation is run until those facts are supplied.
    """
    if kind not in {"growth_percent", "margin_percent"}:
        raise ValueError("Unknown calculation")
    for fact in (left, right):
        if fact.get("review_status") != "human_reviewed" or not fact.get("evidence_id"):
            raise ValueError("Reviewed facts with evidence references are required")
        for field in ("metric", "currency", "unit", "period", "scope"):
            if not fact.get(field) or fact[field] == "unknown":
                raise ValueError("Missing fact metadata: " + field)
        if not isinstance(fact.get("value"), str):
            raise ValueError("Use explicit decimal strings, not binary floats")
    for field in ("currency", "unit", "scope"):
        if left[field] != right[field]:
            raise ValueError("Incompatible fact " + field)
    if kind == "growth_percent" and (left["metric"] != right["metric"] or left["period"] == right["period"]):
        raise ValueError("Growth needs the same metric across two explicitly ordered periods")
    if kind == "margin_percent" and (left["period"] != right["period"] or
                                     left["metric"] != "net_profit" or right["metric"] != "revenue"):
        raise ValueError("Net margin needs net profit and revenue in the same period")
    try:
        numerator, denominator = Decimal(left["value"]), Decimal(right["value"])
    except InvalidOperation as exc:
        raise ValueError("Invalid decimal fact value") from exc
    if not numerator.is_finite() or not denominator.is_finite() or denominator <= 0:
        raise ValueError("Calculation needs finite values and a positive denominator")
    value = (numerator / denominator - (1 if kind == "growth_percent" else 0)) * 100
    return {"kind": kind, "value": str(value), "unit": "percent",
            "left_role": "current" if kind == "growth_percent" else "net_profit",
            "right_role": "baseline" if kind == "growth_percent" else "revenue",
            "inputs": [left, right], "historical_availability_validated": False}
