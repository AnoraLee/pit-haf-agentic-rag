"""Explicit synthetic execution scenarios; no exchange rules or PiT certification implied."""

from datetime import date, datetime, timedelta, timezone
from decimal import Context, Decimal, localcontext
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

Amount = Annotated[
    str, StringConstraints(pattern=r"^(?:0|[1-9]\d{0,17})(?:\.\d{1,6})?$", max_length=25)
]
Weight = Annotated[str, StringConstraints(pattern=r"^(?:0(?:\.\d{1,8})?|1(?:\.0{1,8})?)$")]
Symbol = Annotated[str, StringConstraints(pattern=r"^[A-Z][A-Z0-9_]{1,19}$")]
VN_OFFSET = timezone(timedelta(hours=7))


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


def instant(value: str) -> datetime:
    result = datetime.fromisoformat(value)
    if result.tzinfo is None or result.utcoffset() is None:
        raise ValueError("Session times must have an explicit timezone")
    return result


class Session(Contract):
    date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    open_at: str
    close_at: str
    decision_at: str

    @model_validator(mode="after")
    def timeline(self):
        label = date.fromisoformat(self.date)
        times = [instant(v) for v in (self.open_at, self.close_at, self.decision_at)]
        if not times[0] < times[1] <= times[2] or any(
            t.astimezone(VN_OFFSET).date() != label for t in times
        ):
            raise ValueError("Require open < close <= decision on the labelled +07 session date")
        return self


class Bar(Contract):
    session: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    symbol: Symbol
    open: Amount
    high: Amount
    low: Amount
    close: Amount
    volume: int = Field(ge=0, le=10**12)

    @model_validator(mode="after")
    def prices(self):
        o, h, low, c = (Decimal(v) for v in (self.open, self.high, self.low, self.close))
        if low <= 0 or not low <= min(o, c) <= max(o, c) <= h:
            raise ValueError("Require positive prices and low <= open/close <= high")
        return self


class Target(Contract):
    session: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    weights: dict[Symbol, Weight]


class Scenario(Contract):
    kind: Literal["synthetic_execution_diagnostic"]
    adjustment_status: Literal["synthetic_no_corporate_actions"]
    calendar_basis: Literal["explicit_synthetic_sessions"]
    currency: Literal["scenario_units"]
    symbols: list[Symbol] = Field(min_length=1, max_length=100)
    sessions: list[Session] = Field(min_length=2, max_length=10000)
    bars: list[Bar] = Field(min_length=2, max_length=100000)
    targets: list[Target] = Field(max_length=10000)

    @model_validator(mode="after")
    def panel(self):
        dates = [s.date for s in self.sessions]
        if self.symbols != sorted(set(self.symbols)) or dates != sorted(set(dates)):
            raise ValueError("Symbols and sessions must be unique and sorted")
        if any(
            instant(a.decision_at) >= instant(b.open_at)
            for a, b in zip(self.sessions, self.sessions[1:])
        ):
            raise ValueError("Each decision must precede the next supplied session open")
        keys = [(b.session, b.symbol) for b in self.bars]
        expected = {(d, symbol) for d in dates for symbol in self.symbols}
        if len(keys) != len(set(keys)) or set(keys) != expected:
            raise ValueError(
                "Require exactly one bar per supplied session/symbol; never forward-fill or skip gaps"
            )
        target_dates = [t.session for t in self.targets]
        if target_dates != sorted(set(target_dates)) or not set(target_dates) <= set(dates):
            raise ValueError("Targets must have unique sorted dates in the supplied calendar")
        with localcontext(Context(prec=50)):
            for target in self.targets:
                if (
                    set(target.weights) != set(self.symbols)
                    or sum(map(Decimal, target.weights.values())) > 1
                ):
                    raise ValueError(
                        "Every target must cover the fixed universe with nonnegative weights summing to <= 1"
                    )
        return self


class ExecutionConfig(Contract):
    protocol: Literal["synthetic_execution_v0.1"]
    initial_cash: Amount
    lot_size: int = Field(ge=1, le=10**6)
    buy_fee_bps: int = Field(ge=0, le=1000)
    sell_fee_bps: int = Field(ge=0, le=1000)
    slippage_bps: int = Field(ge=0, le=1000)
    participation_bps: int = Field(ge=1, le=10000)
    share_settlement_sessions: int = Field(ge=0, le=20)
    sale_cash_settlement_sessions: int = Field(ge=0, le=20)

    @model_validator(mode="after")
    def capital(self):
        if Decimal(self.initial_cash) <= 0:
            raise ValueError("Initial cash must be positive")
        return self
