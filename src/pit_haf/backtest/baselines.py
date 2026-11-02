"""Q0/Q1 scheduling mechanics for synthetic diagnostics, without prediction labels."""

from decimal import ROUND_FLOOR, Context, Decimal, localcontext

from pit_haf.backtest.contracts import Scenario
from pit_haf.backtest.engine import literal


def schedule(scenario: Scenario, baseline="manual", rebalance_every=None):
    if baseline not in {"manual", "Q0", "Q1"}:
        raise ValueError("Supported synthetic policies: manual, Q0, Q1")
    if baseline == "Q1":
        if type(rebalance_every) is not int or rebalance_every < 1:
            raise ValueError("Q1 requires a positive fixed rebalance interval in supplied sessions")
    elif rebalance_every is not None:
        raise ValueError("Only Q1 accepts a rebalance interval")
    if baseline == "manual":
        return Scenario.model_validate(scenario.model_dump())
    with localcontext(Context(prec=50)):
        weight = literal(
            (Decimal(1) / len(scenario.symbols)).quantize(
                Decimal("0.00000001"), rounding=ROUND_FLOOR
            )
        )
    dates = scenario.sessions[:1] if baseline == "Q0" else scenario.sessions[::rebalance_every]
    return Scenario.model_validate(
        {
            **scenario.model_dump(),
            "targets": [
                {"session": s.date, "weights": dict.fromkeys(scenario.symbols, weight)}
                for s in dates
            ],
        }
    )
