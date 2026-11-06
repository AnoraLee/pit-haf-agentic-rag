"""Explicit synthetic entitlements; portfolio ownership and legal eligibility are caller inputs."""

from decimal import Context, Decimal, localcontext
from typing import Literal

from pydantic import Field, TypeAdapter, model_validator

from pit_haf.backtest.contracts import Amount, Contract, Symbol, instant
from pit_haf.backtest.engine import literal
from pit_haf.backtest.timed_contracts import Timestamp


class Entitlement(Contract):
    kind: Literal["synthetic_entitlement_instruction"]
    event_id: str = Field(pattern=r"^[a-z][a-z0-9_]{1,60}$")
    symbol: Symbol
    economic_at: Timestamp
    cash_per_share: Amount
    cash_tax_bps: int = Field(ge=0, le=10000)
    cash_available_at: Timestamp | None
    ratio_old: int = Field(ge=1, le=10**6)
    ratio_new: int = Field(ge=0, le=10**6)
    shares_available_at: Timestamp | None
    fraction_policy: Literal["floor_holder_total_discard_fraction"]

    @model_validator(mode="after")
    def timeline(self):
        cash = Decimal(self.cash_per_share) > 0
        if not cash and not self.ratio_new:
            raise ValueError("Entitlement must distribute cash or new shares")
        if (
            cash != (self.cash_available_at is not None)
            or bool(self.ratio_new) != (self.shares_available_at is not None)
            or (not cash and self.cash_tax_bps)
        ):
            raise ValueError("Availability must match each nonzero distribution")
        for at in [self.cash_available_at, self.shares_available_at]:
            if at is not None and instant(at) < instant(self.economic_at):
                raise ValueError("Distribution cannot be available before recognition")
        return self


class CorporateLedger:
    """Pending rights and delivery receipts, separate from price/position adjustment.

    Caller declares eligible holder quantity at the economic instant; this module
    does not derive entitlement from a record date, guessed ex-date or daily bars.
    Only whole new shares are valued; explicitly discarded fractions are logged.
    """

    def __init__(self, *, price_basis="synthetic_unadjusted_marks"):
        if price_basis != "synthetic_unadjusted_marks":
            raise ValueError("Corporate ledger requires declared synthetic unadjusted marks")
        self._clock = None
        self._seen = set()
        self._claims = []
        self._receipts = []
        self._journal = []

    def _advance(self, at):
        now = instant(at)
        if self._clock is not None and now < self._clock:
            raise ValueError("Corporate ledger time cannot move backwards")
        self._clock = now
        due = sorted(
            (c for c in self._claims if instant(c["available_at"]) <= now),
            key=lambda c: (instant(c["available_at"]), c["event_id"], c["kind"]),
        )
        for claim in due:
            receipt = dict(claim) | {"observed_at": at}
            self._receipts.append(receipt)
            self._journal.append(
                receipt
                | {"event": "cash_credited" if claim["kind"] == "cash" else "shares_available"}
            )
        self._claims = [c for c in self._claims if instant(c["available_at"]) > now]

    def recognize(self, instruction: Entitlement, eligible_quantity: int, *, at: str):
        instruction = Entitlement.model_validate(instruction.model_dump())
        if type(eligible_quantity) is not int or not 0 <= eligible_quantity <= 10**12:
            raise ValueError("Eligible holder quantity must be a nonnegative whole number")
        if instruction.event_id in self._seen:
            raise ValueError("Corporate event was already recognized")
        if instant(at) != instant(instruction.economic_at):
            raise ValueError("Recognition must use the declared economic instant")
        self._advance(at)
        self._seen.add(instruction.event_id)
        with localcontext(Context(prec=50)):
            gross = Decimal(instruction.cash_per_share) * eligible_quantity
            tax = gross * instruction.cash_tax_bps / 10000
            net = gross - tax
            whole, fraction = divmod(
                eligible_quantity * instruction.ratio_new, instruction.ratio_old
            )
            base = {"event_id": instruction.event_id, "symbol": instruction.symbol}
            self._journal.append(
                base
                | {
                    "event": "entitlement_recognized",
                    "at": at,
                    "eligible_quantity": eligible_quantity,
                    "eligible_quantity_basis": "caller_declared_synthetic_holder_quantity",
                    "gross_cash": literal(gross),
                    "cash_tax": literal(tax),
                    "net_cash": literal(net),
                    "new_shares": whole,
                    "discarded_fraction_numerator": fraction,
                    "discarded_fraction_denominator": instruction.ratio_old,
                }
            )
            if net:
                self._claims.append(
                    base
                    | {
                        "kind": "cash",
                        "amount": literal(net),
                        "available_at": instruction.cash_available_at,
                    }
                )
            if whole:
                self._claims.append(
                    base
                    | {
                        "kind": "stock",
                        "quantity": whole,
                        "available_at": instruction.shares_available_at,
                    }
                )
        self._advance(at)

    def release(self, at: str):
        self._advance(at)
        return self.state()

    def state(self):
        # JSON containers are copies; callers cannot mutate inventory through a receipt.
        return {
            "pending": [dict(c) for c in self._claims],
            "receipts": [dict(r) for r in self._receipts],
            "journal": [dict(e) for e in self._journal],
            "state_at": self._clock.isoformat() if self._clock is not None else None,
            "research_result": False,
            "independent_gold": False,
            "price_basis": "synthetic_unadjusted_marks",
            "currency": "synthetic_scenario_units",
        }

    def pending_value(self, prices):
        symbols = {c["symbol"] for c in self._claims if c["kind"] == "stock"}
        if not isinstance(prices, dict) or set(prices) != symbols:
            raise ValueError("Supply one positive finite string mark per pending stock symbol")
        for value in prices.values():
            TypeAdapter(Amount).validate_python(value, strict=True)
            if Decimal(value) <= 0:
                raise ValueError("Pending share mark must be positive")
        with localcontext(Context(prec=50)):
            cash = sum(
                (Decimal(c["amount"]) for c in self._claims if c["kind"] == "cash"), Decimal(0)
            )
            stock = sum(
                (
                    Decimal(prices[c["symbol"]]) * c["quantity"]
                    for c in self._claims
                    if c["kind"] == "stock"
                ),
                Decimal(0),
            )
            return {
                "net_cash_receivable": literal(cash),
                "pending_stock_value": literal(stock),
                "total_pending_value": literal(cash + stock),
            }


def demo():
    with localcontext(Context(prec=50)):
        return _demo()


def _demo():
    """Twenty synthetic shares: 116 -> 100, one cash unit plus 15% new stock."""
    action = Entitlement.model_validate(
        {
            "kind": "synthetic_entitlement_instruction",
            "event_id": "synthetic_distribution",
            "symbol": "SYN_A",
            "economic_at": "2024-01-03T09:00:00+07:00",
            "cash_per_share": "1",
            "cash_tax_bps": 0,
            "cash_available_at": "2024-01-05T13:00:00+07:00",
            "ratio_old": 20,
            "ratio_new": 3,
            "shares_available_at": "2024-01-08T09:00:00+07:00",
            "fraction_policy": "floor_holder_total_discard_fraction",
        }
    )
    ledger = CorporateLedger()
    ledger.recognize(action, 20, at=action.economic_at)
    checkpoints = []
    for at in [
        "2024-01-03T15:00:00+07:00",
        "2024-01-05T09:00:00+07:00",
        "2024-01-05T15:00:00+07:00",
        "2024-01-08T09:00:00+07:00",
    ]:
        state = ledger.release(at)
        receipts = state["receipts"]
        cash = sum((Decimal(r["amount"]) for r in receipts if r["kind"] == "cash"), Decimal(0))
        shares = 20 + sum(r["quantity"] for r in receipts if r["kind"] == "stock")
        marks = {"SYN_A": "100"} if any(c["kind"] == "stock" for c in state["pending"]) else {}
        value = ledger.pending_value(marks)
        checkpoints.append(
            {
                "at": at,
                "spendable_dividend_cash": literal(cash),
                "tradable_shares": shares,
                **value,
                "total_value_with_base_position": literal(
                    cash + shares * 100 + Decimal(value["total_pending_value"])
                ),
            }
        )
    return {
        "kind": "synthetic_corporate_ledger_diagnostic",
        "research_result": False,
        "initial_value": "2320",
        "checkpoints": checkpoints,
        "ledger": ledger.state(),
        "assumptions": {
            "price_basis": "synthetic_unadjusted_marks",
            "cash_tax_bps": 0,
            "eligible_quantity": "declared_fixture_not_inferred_from_record_date",
            "orders_generated": 0,
            "automatic_price_adjustment": False,
        },
    }
