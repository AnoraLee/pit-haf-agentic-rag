"""Versioned synthetic execution with timestamped stock and cash availability."""

from decimal import Context, Decimal, localcontext

from pit_haf.backtest.contracts import VN_OFFSET, instant
from pit_haf.backtest.engine import literal, lots
from pit_haf.backtest.timed_contracts import TimedConfig, TimedScenario, settlement_schedule


def simulate(scenario: TimedScenario, config: TimedConfig):
    # Validate copies too: nested lists/dicts in frozen Pydantic models remain mutable.
    scenario = TimedScenario.model_validate(scenario.model_dump())
    config = TimedConfig.model_validate(config.model_dump())
    schedule = settlement_schedule(scenario, config)
    with localcontext(Context(prec=50)):
        return _simulate(scenario.market, config, schedule)


def _simulate(scenario, config, schedule):
    cash = Decimal(0)
    initial = Decimal(config.initial_cash)
    holdings = {s: [] for s in scenario.symbols}
    receivables, orders, trades, cash_ledger, curve = [], [], [], [], []
    queue, pending, settlement_events = [], [], []
    timetable = {row["trade_session"]: row for row in schedule}
    bars = {(b.session, b.symbol): b for b in scenario.bars}
    targets = {t.session: t for t in scenario.targets}
    total_fees = total_slippage = total_notional = Decimal(0)

    def balance(kind, amount, at, observed_at, order_id=None):
        nonlocal cash
        cash += amount
        if cash < 0:
            raise AssertionError("Negative available cash")
        cash_ledger.append(
            {
                "event": kind,
                "session": instant(at).astimezone(VN_OFFSET).date().isoformat(),
                "at": at,
                "observed_at": observed_at,
                "order_id": order_id,
                "amount": literal(amount),
                "cash_after": literal(cash),
            }
        )

    def release_until(observed_at):
        nonlocal pending, receivables
        due = sorted(
            (p for p in pending if instant(p["at"]) <= instant(observed_at)),
            key=lambda p: (instant(p["at"]), p["order_id"], p["event"]),
        )
        for item in due:
            if item["event"] == "shares_released":
                item["asset"]["settled"] = True
            else:
                balance(
                    "sale_cash_released",
                    item["asset"]["amount"],
                    item["at"],
                    observed_at,
                    item["order_id"],
                )
                receivables.remove(item["asset"])
            settlement_events.append(
                {k: v for k, v in item.items() if k != "asset"} | {"observed_at": observed_at}
            )
        pending = [p for p in pending if instant(p["at"]) > instant(observed_at)]

    first_open = scenario.sessions[0].open_at
    balance("initial_cash", initial, first_open, first_open)
    for index, session in enumerate(scenario.sessions):
        release_until(session.open_at)
        # Sell first; deterministic alphabetical allocation within each side.
        for order in sorted(queue, key=lambda o: (o["side"] != "sell", o["symbol"])):
            symbol, side = order["symbol"], order["side"]
            bar = bars[(session.date, symbol)]
            reference = Decimal(bar.open)
            price = reference * (
                1 + Decimal(config.slippage_bps) / 10000 * (1 if side == "buy" else -1)
            )
            fee_rate = Decimal(config.buy_fee_bps if side == "buy" else config.sell_fee_bps) / 10000
            volume_cap = lots(
                Decimal(bar.volume) * config.participation_bps / 10000, config.lot_size
            )
            limits = {"requested": order["requested_quantity"], "volume_cap": volume_cap}
            if not Decimal(bar.low) <= price <= Decimal(bar.high):
                limits["outside_bar_range"] = 0
            if side == "buy":
                limits["available_cash"] = lots(cash / (price * (1 + fee_rate)), config.lot_size)
            else:
                limits["settled_shares"] = sum(
                    lot["quantity"] for lot in holdings[symbol] if lot["settled"]
                )
            quantity = min(limits.values())
            reasons = [
                name
                for name, limit in limits.items()
                if name != "requested" and limit < order["requested_quantity"]
            ]
            order.update(
                execution_session=session.date,
                execution_at=session.open_at,
                open_reference=literal(reference),
                fill_price=literal(price) if quantity else None,
                filled_quantity=quantity,
                status="filled"
                if quantity == order["requested_quantity"]
                else "partial"
                if quantity
                else "unfilled",
                reasons=reasons,
            )
            if not quantity:
                order["fee"] = "0"
                continue
            notional, fee = price * quantity, price * quantity * fee_rate
            slippage = abs(price - reference) * quantity
            total_fees += fee
            total_slippage += slippage
            total_notional += notional
            order["fee"] = literal(fee)
            if side == "buy":
                balance(
                    "buy_debit",
                    -(notional + fee),
                    session.open_at,
                    session.open_at,
                    order["order_id"],
                )
                available_at = timetable[session.date]["shares_available_at"]
                asset = {
                    "quantity": quantity,
                    "available_at": available_at,
                    "settled": False,
                    "buy_order_id": order["order_id"],
                }
                holdings[symbol].append(asset)
                pending.append(
                    {
                        "event": "shares_released",
                        "at": available_at,
                        "order_id": order["order_id"],
                        "symbol": symbol,
                        "quantity": quantity,
                        "amount": None,
                        "asset": asset,
                    }
                )
                cash_effect = -(notional + fee)
            else:
                remaining = quantity
                for lot in holdings[symbol]:
                    if lot["settled"]:
                        sold = min(remaining, lot["quantity"])
                        lot["quantity"] -= sold
                        remaining -= sold
                holdings[symbol] = [lot for lot in holdings[symbol] if lot["quantity"]]
                if remaining:
                    raise AssertionError("Sold unavailable shares")
                cash_effect = notional - fee
                available_at = timetable[session.date]["sale_cash_available_at"]
                asset = {
                    "amount": cash_effect,
                    "available_at": available_at,
                    "order_id": order["order_id"],
                }
                receivables.append(asset)
                pending.append(
                    {
                        "event": "sale_cash_released",
                        "at": available_at,
                        "order_id": order["order_id"],
                        "symbol": symbol,
                        "quantity": None,
                        "amount": literal(cash_effect),
                        "asset": asset,
                    }
                )
            # T+0 at the open can fund the next order; a later intraday time cannot.
            release_until(session.open_at)
            trades.append(
                {
                    "order_id": order["order_id"],
                    "session": session.date,
                    "at": session.open_at,
                    "symbol": symbol,
                    "side": side,
                    "quantity": quantity,
                    "open_reference": literal(reference),
                    "price": literal(price),
                    "notional": literal(notional),
                    "fee": literal(fee),
                    "slippage_cost": literal(slippage),
                    "cash_effect_including_unsettled": literal(cash_effect),
                    "settlement_available_at": available_at,
                }
            )
        queue = []
        release_until(session.close_at)
        quantities = {s: sum(lot["quantity"] for lot in holdings[s]) for s in scenario.symbols}
        values = {
            s: Decimal(bars[(session.date, s)].close) * quantities[s] for s in scenario.symbols
        }
        unsettled_cash = sum((r["amount"] for r in receivables), Decimal(0))
        nav = cash + unsettled_cash + sum(values.values())
        curve.append(
            {
                "session": session.date,
                "at": session.close_at,
                "available_cash": literal(cash),
                "unsettled_sale_cash": literal(unsettled_cash),
                "equity": literal(nav),
                "cumulative_fees": literal(total_fees),
                "positions": [
                    {
                        "symbol": s,
                        "quantity": quantities[s],
                        "settled_quantity": sum(
                            lot["quantity"] for lot in holdings[s] if lot["settled"]
                        ),
                        "close": bars[(session.date, s)].close,
                        "market_value": literal(values[s]),
                    }
                    for s in scenario.symbols
                ],
            }
        )
        # Releases after the close affect decision state, never the prior close snapshot.
        release_until(session.decision_at)
        if session.date not in targets:
            continue
        for symbol in scenario.symbols:
            target = targets[session.date].weights[symbol]
            close = Decimal(bars[(session.date, symbol)].close)
            wanted = lots(Decimal(target) * nav / close, config.lot_size)
            delta = wanted - quantities[symbol]
            if not delta:
                continue
            order = {
                "order_id": f"O{len(orders) + 1:06d}",
                "symbol": symbol,
                "side": "buy" if delta > 0 else "sell",
                "signal_session": session.date,
                "signal_at": session.decision_at,
                "target_weight": target,
                "sizing_nav": literal(nav),
                "sizing_close": literal(close),
                "requested_quantity": abs(delta),
                "execution_session": None,
                "execution_at": None,
                "open_reference": None,
                "fill_price": None,
                "filled_quantity": 0,
                "fee": "0",
                "status": "expired",
                "reasons": ["no_next_session"],
            }
            orders.append(order)
            if index + 1 < len(scenario.sessions):
                queue.append(order)
    final = Decimal(curve[-1]["equity"])
    peak, drawdown = initial, Decimal(0)
    for row in curve:
        value = Decimal(row["equity"])
        peak = max(peak, value)
        drawdown = max(drawdown, 1 - value / peak)
    mean_nav = sum(Decimal(row["equity"]) for row in curve) / len(curve)
    return {
        "protocol": config.protocol,
        "kind": scenario.kind,
        "research_result": False,
        "eligible_for_execution": False,
        "venue_calendar_verified": False,
        "historical_availability_validated": False,
        "independent_gold": False,
        "orders": orders,
        "trades": trades,
        "cash_ledger": cash_ledger,
        "equity_curve": curve,
        "settlement_schedule": schedule,
        "settlement_events": settlement_events,
        "state_at": scenario.sessions[-1].decision_at,
        "ending_available_cash": literal(cash),
        "ending_lots": [{"symbol": s, **lot} for s in scenario.symbols for lot in holdings[s]],
        "ending_receivables": [{**r, "amount": literal(r["amount"])} for r in receivables],
        "metrics": {
            "initial_cash": literal(initial),
            "ending_equity": literal(final),
            "net_return": literal(final / initial - 1),
            "max_drawdown": literal(drawdown),
            "fees_paid": literal(total_fees),
            "slippage_cost": literal(total_slippage),
            "traded_notional": literal(total_notional),
            "two_sided_turnover": literal(total_notional / mean_nav),
            "orders": len(orders),
            "fills": len(trades),
            "fully_filled_orders": sum(o["status"] == "filled" for o in orders),
            "partially_filled_orders": sum(o["status"] == "partial" for o in orders),
            "unfilled_orders": sum(o["status"] == "unfilled" for o in orders),
            "expired_orders": sum(o["status"] == "expired" for o in orders),
            "annualized_return": None,
            "sharpe": None,
            "macro_f1": None,
        },
        "assumptions": {
            "execution": "next_supplied_session_open_only; day_orders_without_automatic_retry",
            "sizing": "target_NAV_and_close_on_decision_session; round_down_to_lots",
            "allocation": "sells_then_buys; alphabetical_symbols; cash_and_volume_caps; partial_fills_allowed",
            "valuation": "close_marks_including_unsettled_shares_and_sale_receivables; no_terminal_liquidation",
            "settlement": "explicit_settlement_day_lags_and_availability_instants; release_time_selected_on_settlement_date",
            "state_checkpoints": "release_at_or_before_open_close_decision; inclusive_boundary; actual_and_observed_time_logged",
            "precision": "Decimal_50_digits; no_currency_tick_or_fee_rounding",
            "liquidity": "daily_volume_cap_and_OHLC_range_are_ex_post_proxies_not_open_auction_depth",
            "limitations": [
                "synthetic_only",
                "no_verified_HOSE_or_VSDC_calendar_or_broker_availability",
                "open_only_execution_cannot_trade_at_afternoon_release",
                "no_corporate_actions_dividends_price_limits_or_delisting",
                "no_intraday_queue_or_real_fill_guarantee",
                "external_target_information_availability_not_verified",
                "no_agent_prediction_horizon_exit_policy_or_research_baseline_results",
            ],
        },
    }
