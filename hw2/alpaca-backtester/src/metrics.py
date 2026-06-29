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
    equity = result.equity
    returns = result.returns.dropna()
    initial = result.initial_capital
    final = float(equity.iloc[-1])

    # Total return
    total_return = final / initial - 1.0

    # Time span in years
    days = (equity.index[-1] - equity.index[0]).days
    years = max(days / 365.25, 1e-9)

    # CAGR
    cagr = (final / initial) ** (1 / years) - 1.0 if final > 0 else -1.0

    # Annualised volatility
    volatility = returns.std(ddof=0) * np.sqrt(TRADING_DAYS)

    # Sharpe (excess return over rf)
    rf_daily = (1 + risk_free) ** (1 / TRADING_DAYS) - 1
    excess = returns - rf_daily
    sharpe = (
        excess.mean() / excess.std(ddof=0) * np.sqrt(TRADING_DAYS)
        if excess.std(ddof=0) > 0
        else 0.0
    )

    # Sortino (downside deviation only)
    downside = excess[excess < 0]
    downside_dev = downside.std(ddof=0) * np.sqrt(TRADING_DAYS)
    sortino = (
        excess.mean() * TRADING_DAYS / downside_dev if downside_dev > 0 else np.nan
    )

    # Max drawdown
    dd = _drawdown_series(equity)
    max_drawdown = float(dd.min())

    # Win rate over completed round-trips
    trades = result.trades
    if trades is not None and not trades.empty and "win" in trades.columns:
        closed = trades["win"].dropna()
        num_trades = int(len(closed))
        win_rate = float(closed.mean()) if num_trades else np.nan
    else:
        num_trades = 0
        win_rate = np.nan

    return {
        "total_return": total_return,
        "cagr": cagr,
        "volatility": volatility,
        "sharpe": sharpe,
        "sortino": sortino,
        "max_drawdown": max_drawdown,
        "win_rate": win_rate,
        "num_trades": num_trades,
        "final_equity": final,
    }


def drawdown(result) -> pd.Series:
    """Drawdown series for plotting."""
    return _drawdown_series(result.equity)


def metrics_table(results: dict, risk_free: float = 0.0) -> pd.DataFrame:
    """
    Build a comparison DataFrame across many strategies.

    ``results`` maps display-name -> BacktestResult.
    """
    rows = {}
    for name, res in results.items():
        rows[name] = compute_metrics(res, risk_free=risk_free)
    table = pd.DataFrame(rows).T
    ordered = [
        "total_return",
        "cagr",
        "volatility",
        "sharpe",
        "sortino",
        "max_drawdown",
        "win_rate",
        "num_trades",
        "final_equity",
    ]
    return table[ordered]


def format_metrics_table(table: pd.DataFrame) -> pd.DataFrame:
    """Human-readable version (percentages, rounded ratios)."""
    fmt = pd.DataFrame(index=table.index)
    fmt["Total Return"] = (table["total_return"] * 100).map("{:.1f}%".format)
    fmt["CAGR"] = (table["cagr"] * 100).map("{:.1f}%".format)
    fmt["Volatility"] = (table["volatility"] * 100).map("{:.1f}%".format)
    fmt["Sharpe"] = table["sharpe"].map("{:.2f}".format)
    fmt["Sortino"] = table["sortino"].map(
        lambda x: "n/a" if pd.isna(x) else f"{x:.2f}"
    )
    fmt["Max Drawdown"] = (table["max_drawdown"] * 100).map("{:.1f}%".format)
    fmt["Win Rate"] = table["win_rate"].map(
        lambda x: "n/a" if pd.isna(x) else f"{x*100:.0f}%"
    )
    fmt["# Trades"] = table["num_trades"].astype(int)
    return fmt
