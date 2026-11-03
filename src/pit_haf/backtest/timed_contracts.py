"""Explicit settlement days and availability instants; synthetic inputs only."""

from datetime import date
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import Field, StringConstraints, model_validator

from pit_haf.backtest.contracts import VN_OFFSET, Amount, Contract, Scenario, instant

Timestamp = Annotated[
    str,
    StringConstraints(
        pattern=r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|[+-]\d{2}:\d{2})$"
    ),
]


class SettlementDay(Contract):
    date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    shares_at: Timestamp
    cash_at: Timestamp

    @model_validator(mode="after")
    def labelled_instants(self):
        label = date.fromisoformat(self.date)
        if any(
            instant(value).astimezone(VN_OFFSET).date() != label
            for value in (self.shares_at, self.cash_at)
        ):
            raise ValueError("Settlement instants must fall on the labelled +07 date")
        return self


class TimedScenario(Contract):
    market: Scenario
    settlement_basis: Literal["explicit_synthetic_settlement_days"]
    settlement_days: list[SettlementDay] = Field(min_length=2, max_length=10040)

    @model_validator(mode="after")
    def calendar(self):
        dates = [day.date for day in self.settlement_days]
        if dates != sorted(set(dates)):
            raise ValueError("Settlement days must be unique and sorted")
        if not {s.date for s in self.market.sessions} <= set(dates):
            raise ValueError("Every trading session must belong to the settlement calendar")
        return self


class TimedConfig(Contract):
    protocol: Literal["synthetic_timed_execution_v0.1"]
    initial_cash: Amount
    lot_size: int = Field(ge=1, le=10**6)
    buy_fee_bps: int = Field(ge=0, le=1000)
    sell_fee_bps: int = Field(ge=0, le=1000)
    slippage_bps: int = Field(ge=0, le=1000)
    participation_bps: int = Field(ge=1, le=10000)
    share_lag_days: int = Field(ge=0, le=20)
    sale_cash_lag_days: int = Field(ge=0, le=20)

    @model_validator(mode="after")
    def capital(self):
        if Decimal(self.initial_cash) <= 0:
            raise ValueError("Initial cash must be positive")
        return self


def settlement_schedule(scenario: TimedScenario, config: TimedConfig):
    """Resolve by explicit day index, then take the release time on that day.

    The completion time belongs to the settlement date, not the trade date.
    No weekdays, holidays, broker availability or effective rules are inferred.
    Require coverage even for sessions where a selected strategy will not trade.
    """
    days = scenario.settlement_days
    indices = {day.date: i for i, day in enumerate(days)}
    rows = []
    for session in scenario.market.sessions:
        index = indices[session.date]
        if index + max(config.share_lag_days, config.sale_cash_lag_days) >= len(days):
            raise ValueError("Settlement calendar needs an explicit tail beyond every trade date")
        shares = days[index + config.share_lag_days]
        cash = days[index + config.sale_cash_lag_days]
        if min(instant(shares.shares_at), instant(cash.cash_at)) < instant(session.open_at):
            raise ValueError("Settlement availability cannot precede the trade open")
        rows.append(
            {
                "trade_session": session.date,
                "trade_at": session.open_at,
                "share_settlement_date": shares.date,
                "shares_available_at": shares.shares_at,
                "cash_settlement_date": cash.date,
                "sale_cash_available_at": cash.cash_at,
            }
        )
    return rows
