#!/usr/bin/env python3
"""
main.py
=======
End-to-end driver for the Alpaca backtesting platform.

Usage
-----
    python main.py --ticker AAPL --years 5
    python main.py --ticker SPY --years 7 --risk-free 0.04

With ALPACA_API_KEY / ALPACA_SECRET_KEY set in the environment, data is pulled
live from Alpaca. Without them (or without network access), a deterministic
synthetic series is generated so the pipeline still runs end-to-end.

Outputs
-------
    charts/equity_curve.png
    charts/drawdowns.png
    charts/price_<strategy>.png
    report/final_report.pdf
    report/performance_<ticker>.csv
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from src import backtest, data_loader, indicators, metrics, report, strategies, visualize

ROOT = Path(__file__).resolve().parent
CHARTS = ROOT / "charts"
REPORT = ROOT / "report"


def build_discussion(ticker, raw, fmt, source) -> str:
    """Generate a data-driven narrative for the report's discussion section."""
    bh = raw.loc["Buy & Hold"]
    best_sharpe = raw["sharpe"].idxmax()
    best_return = raw["total_return"].idxmax()
    best_dd = raw["max_drawdown"].idxmax()  # closest to 0 = smallest drawdown

    lines = []
    lines.append(
        f"Over the {len(raw)-1} active strategies tested on {ticker}, "
        f"<b>{best_sharpe}</b> delivered the strongest risk-adjusted performance "
        f"with a Sharpe ratio of {raw.loc[best_sharpe,'sharpe']:.2f}, which is "
        f"the headline answer to the project question: on a risk-adjusted basis "
        f"this strategy was the best performer in this sample."
    )
    lines.append(
        f"On raw total return, <b>{best_return}</b> led at "
        f"{raw.loc[best_return,'total_return']*100:.1f}%, versus the Buy &amp; "
        f"Hold benchmark at {bh['total_return']*100:.1f}%. Higher absolute "
        f"return does not always coincide with the best Sharpe: an aggressive "
        f"strategy can win on return while taking on volatility that a "
        f"risk-adjusted lens penalises."
    )
    lines.append(
        f"For capital preservation, <b>{best_dd}</b> had the shallowest maximum "
        f"drawdown ({raw.loc[best_dd,'max_drawdown']*100:.1f}%). The active "
        f"strategies spend meaningful time in cash, so they typically cut "
        f"drawdowns relative to always-invested Buy &amp; Hold — the trade-off "
        f"is that they also miss part of sustained up-moves, which is visible "
        f"in the equity curves."
    )
    lines.append(
        "Reading the strategies individually: the trend-following rules only "
        "engage when MACD, ADX and the moving-average filter agree, so it sits "
        "out choppy ranges and concentrates risk in established trends. Mean "
        "reversion does the opposite — it buys statistically stretched "
        "selloffs (RSI&lt;30 and a close below the lower Bollinger Band), which "
        "fires rarely and can underperform badly when a downtrend keeps going "
        "rather than reverting. The custom triple-confirmation strategy is the "
        "most selective: it only buys pullbacks inside a confirmed uptrend "
        "(EMA structure), with momentum turning up (RSI crossing 50) and "
        "volume confirming accumulation (CMF&gt;0)."
    )
    lines.append(
        "Caveats: results are sensitive to the chosen window and parameters "
        "(thresholds, lookbacks), a single ticker is a small sample, and these "
        "backtests exclude taxes and assume fills at the next open with only a "
        "1 bp slippage allowance. A robust conclusion would repeat this across "
        "many tickers and time periods and test parameter stability."
    )
    if source == "synthetic":
        lines.append(
            "<i>Note: this run used the synthetic data fallback because Alpaca "
            "credentials/network were unavailable in this environment. Numbers "
            "are illustrative of the pipeline; set ALPACA_API_KEY and "
            "ALPACA_SECRET_KEY and re-run for live market data.</i>"
        )
    return "\n\n".join(lines)


def run(ticker: str, years: int, risk_free: float, cost_bps: float) -> None:
    print(f"\n=== Backtesting {ticker} over {years}y ===")

    # 1. Data
    df = data_loader.load_data(ticker, years, allow_synthetic=False)
    source = df.attrs.get("source", "unknown")
    print(f"Loaded {len(df)} daily bars  (source: {source}, "
          f"{df.index[0].date()} -> {df.index[-1].date()})")

    # 2. Indicators
    enriched = indicators.add_all_indicators(df)

    # 3. Strategies + 4. Backtests
    results = {}
    results["Buy & Hold"] = backtest.buy_and_hold(enriched)
    for name, fn in strategies.STRATEGIES.items():
        position = fn(enriched)
        results[name] = backtest.run_backtest(
            enriched, position, name=name, cost_bps=cost_bps
        )
        n_trades = int((results[name].trades["side"] == "BUY").sum()) \
            if not results[name].trades.empty else 0
        print(f"  {name:<28} entries: {n_trades}")

    # 5. Metrics
    raw = metrics.metrics_table(results, risk_free=risk_free)
    fmt = metrics.format_metrics_table(raw)
    print("\nPerformance:\n", fmt.to_string())

    REPORT.mkdir(exist_ok=True)
    raw.to_csv(REPORT / f"performance_{ticker}.csv")

    # 6. Charts
    chart_paths = {
        "equity": visualize.equity_curve(results, ticker, CHARTS),
        "drawdown": visualize.drawdown_chart(results, ticker, CHARTS),
        "price": {},
    }
    for name in strategies.STRATEGIES:
        chart_paths["price"][name] = visualize.price_chart(
            enriched, results[name], ticker, CHARTS
        )

    # 7. Report
    discussion = build_discussion(ticker, raw, fmt, source)
    pdf = report.build_report(
        ticker=ticker,
        years=years,
        data_source="Alpaca" if source == "alpaca" else "Synthetic (fallback)",
        fmt_table=fmt,
        raw_table=raw,
        chart_paths=chart_paths,
        out_path=REPORT / "final_report.pdf",
        discussion=discussion,
    )
    print(f"\nReport written: {pdf}")
    print(f"Charts written: {CHARTS}")


def main():
    p = argparse.ArgumentParser(description="Alpaca strategy backtester")
    p.add_argument("--ticker", default="AAPL",
                   help="Symbol, e.g. AAPL MSFT SPY QQQ NVDA")
    p.add_argument("--years", type=int, default=5, help="Lookback in years (>=5)")
    p.add_argument("--risk-free", type=float, default=0.0,
                   help="Annual risk-free rate for Sharpe/Sortino, e.g. 0.04")
    p.add_argument("--cost-bps", type=float, default=1.0,
                   help="Per-trade slippage in basis points")
    args = p.parse_args()
    run(args.ticker.upper(), max(args.years, 5), args.risk_free, args.cost_bps)


if __name__ == "__main__":
    main()
