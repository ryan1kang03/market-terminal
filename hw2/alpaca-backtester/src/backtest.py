"""
backtest.py
===========
A small, reusable, vectorised-ish backtesting engine.

Assumptions (per project spec)
------------------------------
* Initial capital : $100,000
* Long-only       : positions are either fully invested (1) or fully cash (0)
* No leverage     : at most 100% of equity is deployed
* No short selling

Mechanics
---------
* A strategy emits a target position from each day's *close*.
* We shift that target forward one bar and execute at the *next day's open*,
  which removes look-ahead bias.
* Optional per-trade slippage/cost (in basis points) is applied to the traded
  notional whenever the position changes.

The engine returns a ``BacktestResult`` carrying the daily equity curve, daily
returns, the position series, and a trade ledger.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd


@dataclass
class BacktestResult:
    name: str
    equity: pd.Series           # portfolio value over time
    returns: pd.Series          # daily portfolio returns
    position: pd.Series         # 0/1 position actually held each day
    trades: pd.DataFrame        # ledger of executed trades
    initial_capital: float
    meta: dict = field(default_factory=dict)


def run_backtest(
    df: pd.DataFrame,
    position: pd.Series,
    *,
    name: str = "Strategy",
    initial_capital: float = 100_000.0,
    cost_bps: float = 1.0,
    execution: str = "next_open",
) -> BacktestResult:
    """
    Backtest a single 0/1 position series against price data.

    Parameters
    ----------
    df               : OHLCV frame (needs 'open' and 'close').
    position         : target position from the strategy (0 or 1), indexed like df.
    initial_capital  : starting cash.
    cost_bps         : round-trip-agnostic cost applied to each side of a trade,
                       in basis points of traded notional (1 bp = 0.01%).
                       Alpaca equity commissions are $0; this models slippage.
    execution        : 'next_open' (default, realistic) or 'close' (same-bar).
    """
    price_open = df["open"]
    price_close = df["close"]

    # Shift the target so a close-based signal is acted on the following bar.
    if execution == "next_open":
        target = position.shift(1).fillna(0).astype(int)
        exec_price = price_open
    else:  # 'close'
        target = position.fillna(0).astype(int)
        exec_price = price_close

    dates = df.index
    cash = initial_capital
    shares = 0.0
    held = 0  # current position state
    cost_rate = cost_bps / 10_000.0

    equity_curve = np.empty(len(dates))
    held_series = np.zeros(len(dates), dtype=int)
    trades = []

    for i, date in enumerate(dates):
        tgt = int(target.iloc[i])
        px_exec = exec_price.iloc[i]
        px_close = price_close.iloc[i]

        # Execute a transition at this bar's execution price.
        if tgt != held and not np.isnan(px_exec):
            if tgt == 1:  # BUY: deploy all cash
                gross = cash
                cost = gross * cost_rate
                investable = gross - cost
                shares = investable / px_exec
                cash = 0.0
                trades.append(
                    {
                        "date": date,
                        "side": "BUY",
                        "price": px_exec,
                        "shares": shares,
                        "cost": cost,
                        "equity_before": gross,
                    }
                )
            else:  # SELL: liquidate
                proceeds = shares * px_exec
                cost = proceeds * cost_rate
                cash = proceeds - cost
                trades.append(
                    {
                        "date": date,
                        "side": "SELL",
                        "price": px_exec,
                        "shares": shares,
                        "cost": cost,
                        "equity_before": proceeds,
                    }
                )
                shares = 0.0
            held = tgt

        held_series[i] = held
        equity_curve[i] = cash + shares * px_close

    equity = pd.Series(equity_curve, index=dates, name=name)
    returns = equity.pct_change().fillna(0.0)
    held_ser = pd.Series(held_series, index=dates, name="position")
    trade_df = pd.DataFrame(trades)
    if not trade_df.empty:
        trade_df = trade_df.set_index("date")

    # Pair buys/sells into round-trips and tag each as win/loss.
    trade_df = _annotate_round_trips(trade_df)

    return BacktestResult(
        name=name,
        equity=equity,
        returns=returns,
        position=held_ser,
        trades=trade_df,
        initial_capital=initial_capital,
        meta={"cost_bps": cost_bps, "execution": execution},
    )


def buy_and_hold(
    df: pd.DataFrame,
    *,
    name: str = "Buy & Hold",
    initial_capital: float = 100_000.0,
) -> BacktestResult:
    """Benchmark: buy at the first available open, hold to the end."""
    pos = pd.Series(1, index=df.index)
    return run_backtest(
        df, pos, name=name, initial_capital=initial_capital, cost_bps=1.0
    )


def _annotate_round_trips(trades: pd.DataFrame) -> pd.DataFrame:
    """Add a 'pnl' and 'win' column to each SELL closing a prior BUY."""
    if trades.empty:
        return trades
    trades = trades.copy()
    trades["pnl"] = np.nan
    trades["return_pct"] = np.nan
    trades["win"] = pd.NA

    open_buy = None
    for idx, row in trades.iterrows():
        if row["side"] == "BUY":
            open_buy = (idx, row)
        elif row["side"] == "SELL" and open_buy is not None:
            buy_idx, buy = open_buy
            buy_notional = buy["shares"] * buy["price"]
            sell_notional = row["shares"] * row["price"]
            pnl = sell_notional - buy_notional - row["cost"] - buy["cost"]
            trades.loc[idx, "pnl"] = pnl
            trades.loc[idx, "return_pct"] = (
                pnl / buy_notional if buy_notional else np.nan
            )
            trades.loc[idx, "win"] = bool(pnl > 0)
            open_buy = None
    return trades
