"""
visualize.py
============
Chart generation with matplotlib. Every function writes a PNG to ``out_dir`` and
returns the path, so the report builder can embed them.

Charts
------
1. price_chart      : price + key indicators + buy/sell markers for one strategy.
2. equity_curve     : Buy & Hold vs all strategies on one axis.
3. drawdown_chart   : underwater (drawdown) curves for all strategies.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # headless
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from . import metrics

plt.rcParams.update(
    {
        "figure.dpi": 130,
        "savefig.dpi": 130,
        "font.size": 9,
        "axes.grid": True,
        "grid.alpha": 0.25,
        "axes.spines.top": False,
        "axes.spines.right": False,
    }
)

# Consistent colours across charts.
PALETTE = {
    "Buy & Hold": "#7f7f7f",
    "Trend Following": "#1f77b4",
    "Mean Reversion": "#d62728",
    "Custom Triple Confirmation": "#2ca02c",
}


def _color(name: str) -> str:
    return PALETTE.get(name, "#9467bd")


def price_chart(
    df: pd.DataFrame,
    result,
    ticker: str,
    out_dir: Path,
    filename: str | None = None,
) -> Path:
    """
    Price with SMA-50/200 and Bollinger Bands, an RSI subplot, and buy/sell
    markers drawn from the strategy's trade ledger.
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    fname = filename or f"price_{result.name.lower().replace(' ', '_')}.png"
    path = out_dir / fname

    fig, (ax1, ax2) = plt.subplots(
        2, 1, figsize=(11, 6.5), sharex=True,
        gridspec_kw={"height_ratios": [3, 1]},
    )

    ax1.plot(df.index, df["close"], color="#222", lw=1.0, label="Close")
    if "sma_50" in df:
        ax1.plot(df.index, df["sma_50"], color="#1f77b4", lw=0.9, label="SMA 50")
    if "sma_200" in df:
        ax1.plot(df.index, df["sma_200"], color="#ff7f0e", lw=0.9, label="SMA 200")
    if {"bb_upper", "bb_lower"}.issubset(df.columns):
        ax1.plot(df.index, df["bb_upper"], color="#999", lw=0.6, ls="--")
        ax1.plot(df.index, df["bb_lower"], color="#999", lw=0.6, ls="--")
        ax1.fill_between(
            df.index, df["bb_lower"], df["bb_upper"], color="#cccccc", alpha=0.18
        )

    trades = result.trades
    if trades is not None and not trades.empty:
        buys = trades[trades["side"] == "BUY"]
        sells = trades[trades["side"] == "SELL"]
        ax1.scatter(
            buys.index, buys["price"], marker="^", s=70, color="#2ca02c",
            edgecolor="white", linewidth=0.6, zorder=5, label="Buy",
        )
        ax1.scatter(
            sells.index, sells["price"], marker="v", s=70, color="#d62728",
            edgecolor="white", linewidth=0.6, zorder=5, label="Sell",
        )

    ax1.set_title(f"{ticker} — {result.name}: price, indicators & signals")
    ax1.set_ylabel("Price ($)")
    ax1.legend(loc="upper left", ncol=3, fontsize=8, framealpha=0.9)

    # RSI subplot
    if "rsi" in df:
        ax2.plot(df.index, df["rsi"], color="#6a3d9a", lw=0.9)
        ax2.axhline(70, color="#d62728", lw=0.7, ls="--")
        ax2.axhline(30, color="#2ca02c", lw=0.7, ls="--")
        ax2.fill_between(df.index, 30, 70, color="#eee", alpha=0.4)
        ax2.set_ylim(0, 100)
        ax2.set_ylabel("RSI")
    ax2.set_xlabel("Date")
    ax2.xaxis.set_major_locator(mdates.YearLocator())
    ax2.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))

    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)
    return path


def equity_curve(
    results: dict, ticker: str, out_dir: Path, filename: str = "equity_curve.png"
) -> Path:
    """Overlay equity curves for every strategy + benchmark."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / filename

    fig, ax = plt.subplots(figsize=(11, 5.5))
    for name, res in results.items():
        ax.plot(
            res.equity.index, res.equity.values,
            label=name, color=_color(name),
            lw=1.8 if name == "Buy & Hold" else 1.4,
            ls="--" if name == "Buy & Hold" else "-",
        )
    ax.axhline(
        next(iter(results.values())).initial_capital,
        color="#bbb", lw=0.8, ls=":",
    )
    ax.set_title(f"{ticker} — Equity curves (initial $100,000)")
    ax.set_ylabel("Portfolio value ($)")
    ax.set_xlabel("Date")
    ax.yaxis.set_major_formatter(
        plt.FuncFormatter(lambda x, _: f"${x/1000:.0f}k")
    )
    ax.legend(loc="upper left", fontsize=8.5, framealpha=0.9)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)
    return path


def drawdown_chart(
    results: dict, ticker: str, out_dir: Path, filename: str = "drawdowns.png"
) -> Path:
    """Underwater plot comparing drawdowns across strategies."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / filename

    fig, ax = plt.subplots(figsize=(11, 5.0))
    for name, res in results.items():
        dd = metrics.drawdown(res) * 100
        ax.plot(dd.index, dd.values, label=name, color=_color(name), lw=1.2)
    ax.fill_between(
        next(iter(results.values())).equity.index, 0, -0.0001, color="white"
    )
    ax.set_title(f"{ticker} — Drawdown comparison")
    ax.set_ylabel("Drawdown (%)")
    ax.set_xlabel("Date")
    ax.legend(loc="lower left", fontsize=8.5, framealpha=0.9)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)
    return path
