"""
metrics.py
==========
Risk and performance statistics computed from a BacktestResult.

All annualised figures assume 252 trading days. The risk-free rate defaults to
0 but is configurable; pass an annual rate (e.g. 0.04 for 4%).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

TRADING_DAYS = 252


def _drawdown_series(equity: pd.Series) -> pd.Series:
    running_max = equity.cummax()
    return equity / running_max - 1.0


def compute_metrics(result, risk_free: float = 0.0) -> dict:
    """
    Return a dict of headline metrics for one backtest.

    Keys: total_return, cagr, volatility, sharpe, sortino, max_drawdown,
          win_rate, num_trades, final_equity.
    """
    equity  = result.equity
    returns = result.returns.dropna()
    initial = result.initial_capital
    final   = float(equity.iloc[-1])

    total_return = final / initial - 1.0

    days  = (equity.index[-1] - equity.index[0]).days
    years = max(days / 365.25, 1e-9)
    cagr  = (final / initial) ** (1 / years) - 1.0 if final > 0 else -1.0

    volatility = returns.std(ddof=0) * np.sqrt(TRADING_DAYS)

    rf_daily = (1 + risk_free) ** (1 / TRADING_DAYS) - 1
    excess   = returns - rf_daily
    sharpe   = (
        excess.mean() / excess.std(ddof=0) * np.sqrt(TRADING_DAYS)
        if excess.std(ddof=0) > 0 else 0.0
    )

    downside     = excess[excess < 0]
    downside_dev = downside.std(ddof=0) * np.sqrt(TRADING_DAYS)
    sortino      = (
        excess.mean() * TRADING_DAYS / downside_dev if downside_dev > 0 else np.nan
    )

    dd           = _drawdown_series(equity)
    max_drawdown = float(dd.min())

    trades = result.trades
    if trades is not None and not trades.empty and "win" in trades.columns:
        closed    = trades["win"].dropna()
        num_trades = int(len(closed))
        win_rate   = float(closed.mean()) if num_trades else np.nan
    else:
        num_trades = 0
        win_rate   = np.nan

    return {
        "total_return": total_return,
        "cagr":         cagr,
        "volatility":   volatility,
        "sharpe":       sharpe,
        "sortino":      sortino,
        "max_drawdown": max_drawdown,
        "win_rate":     win_rate,
        "num_trades":   num_trades,
        "final_equity": final,
    }


def trade_statistics(result) -> dict:
    """
    Detailed trade-level statistics from the round-trip ledger.

    Returns keys: num_trades, win_rate, avg_winner_pct, avg_loser_pct,
    profit_factor, avg_trade_pct, best_trade_pct, worst_trade_pct,
    avg_hold_days.
    """
    trades = result.trades
    if trades is None or trades.empty or "pnl" not in trades.columns:
        return {k: np.nan for k in [
            "num_trades", "win_rate", "avg_winner_pct", "avg_loser_pct",
            "profit_factor", "avg_trade_pct", "best_trade_pct",
            "worst_trade_pct", "avg_hold_days"
        ]}

    sells = trades[(trades["side"] == "SELL") & trades["pnl"].notna()].copy()
    if sells.empty:
        return {k: np.nan for k in [
            "num_trades", "win_rate", "avg_winner_pct", "avg_loser_pct",
            "profit_factor", "avg_trade_pct", "best_trade_pct",
            "worst_trade_pct", "avg_hold_days"
        ]}

    winners = sells[sells["pnl"] > 0]
    losers  = sells[sells["pnl"] < 0]

    gross_profit = winners["pnl"].sum()
    gross_loss   = abs(losers["pnl"].sum())
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else np.inf

    # Pair buys and sells to estimate hold duration.
    buys  = trades[trades["side"] == "BUY"]
    hold_days = []
    buy_dates  = list(buys.index)
    sell_dates = list(sells.index)
    for sell_dt in sell_dates:
        prior = [d for d in buy_dates if d <= sell_dt]
        if prior:
            hold_days.append((sell_dt - max(prior)).days)

    return {
        "num_trades":      len(sells),
        "win_rate":        len(winners) / len(sells),
        "avg_winner_pct":  winners["return_pct"].mean() if not winners.empty else np.nan,
        "avg_loser_pct":   losers["return_pct"].mean()  if not losers.empty  else np.nan,
        "profit_factor":   profit_factor,
        "avg_trade_pct":   sells["return_pct"].mean(),
        "best_trade_pct":  sells["return_pct"].max(),
        "worst_trade_pct": sells["return_pct"].min(),
        "avg_hold_days":   np.mean(hold_days) if hold_days else np.nan,
    }


def yearly_returns_table(results: dict) -> pd.DataFrame:
    """
    Calendar-year returns for every strategy.

    Rows = years, columns = strategy names.
    """
    frames = {}
    for name, res in results.items():
        eq = res.equity
        # Last trading day in each calendar year
        yearly_eq = eq.resample("YE").last()
        # First available equity value (start of each year or very first bar)
        yr_ret = yearly_eq.pct_change()
        # For the first year, compute from the initial capital
        first_date = eq.index[0]
        first_year = first_date.year
        first_year_end = yearly_eq[yearly_eq.index.year == first_year]
        if not first_year_end.empty:
            first_ret = float(first_year_end.iloc[-1]) / res.initial_capital - 1
            yr_ret.iloc[0] = first_ret
        frames[name] = yr_ret
    df = pd.DataFrame(frames)
    df.index = df.index.year
    df.index.name = "Year"
    return df


def drawdown(result) -> pd.Series:
    """Drawdown series for plotting."""
    return _drawdown_series(result.equity)


def metrics_table(results: dict, risk_free: float = 0.0) -> pd.DataFrame:
    """Build a comparison DataFrame across many strategies."""
    rows = {}
    for name, res in results.items():
        rows[name] = compute_metrics(res, risk_free=risk_free)
    table = pd.DataFrame(rows).T
    ordered = [
        "total_return", "cagr", "volatility", "sharpe", "sortino",
        "max_drawdown", "win_rate", "num_trades", "final_equity",
    ]
    return table[ordered]


def format_metrics_table(table: pd.DataFrame) -> pd.DataFrame:
    """Human-readable version (percentages, rounded ratios)."""
    fmt = pd.DataFrame(index=table.index)
    fmt["Total Return"] = (table["total_return"] * 100).map("{:.1f}%".format)
    fmt["CAGR"]         = (table["cagr"]         * 100).map("{:.1f}%".format)
    fmt["Volatility"]   = (table["volatility"]   * 100).map("{:.1f}%".format)
    fmt["Sharpe"]       = table["sharpe"].map("{:.2f}".format)
    fmt["Sortino"]      = table["sortino"].map(
        lambda x: "n/a" if pd.isna(x) else f"{x:.2f}"
    )
    fmt["Max Drawdown"] = (table["max_drawdown"] * 100).map("{:.1f}%".format)
    fmt["Win Rate"]     = table["win_rate"].map(
        lambda x: "n/a" if pd.isna(x) else f"{x*100:.0f}%"
    )
    fmt["# Trades"]     = table["num_trades"].astype(int)
    return fmt


def price_stats(df: pd.DataFrame) -> dict:
    """Descriptive statistics on the raw price series for the data section."""
    r = df["close"].pct_change().dropna()
    return {
        "start_price":  float(df["close"].iloc[0]),
        "end_price":    float(df["close"].iloc[-1]),
        "total_return": float(df["close"].iloc[-1] / df["close"].iloc[0] - 1),
        "ann_vol":      float(r.std(ddof=0) * np.sqrt(252)),
        "skewness":     float(r.skew()),
        "kurtosis":     float(r.kurt()),
        "avg_daily_vol": float(df["volume"].mean()),
        "max_1d_gain":  float(r.max()),
        "max_1d_loss":  float(r.min()),
    }
