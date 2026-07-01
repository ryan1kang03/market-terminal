#!/usr/bin/env python3
"""
main.py
=======
End-to-end driver for the Alpaca backtesting platform.

Usage
-----
    python main.py --ticker AAPL --years 5
    python main.py --ticker SPY --years 7 --risk-free 0.04

Credentials are loaded automatically from any .env file found in the
directory tree (APCA_API_KEY_ID / APCA_API_SECRET_KEY or the aliases
ALPACA_API_KEY / ALPACA_SECRET_KEY). Without credentials, a deterministic
synthetic series is used so the pipeline runs end-to-end without a network.

Outputs
-------
    charts/equity_curve.png
    charts/drawdowns.png
    charts/price_<strategy>.png   (one per strategy)
    report/final_report.pdf
    report/performance_<ticker>.csv
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from src import backtest, data_loader, indicators, metrics, report, strategies, visualize

ROOT   = Path(__file__).resolve().parent
CHARTS = ROOT / "charts"
REPORT = ROOT / "report"


# ── Discussion builder ────────────────────────────────────────────────────────

def build_discussion(ticker: str, raw: pd.DataFrame, fmt: pd.DataFrame,
                     source: str, risk_free: float) -> str:
    """
    Generate a thorough, data-driven narrative for the report's discussion section.
    Each logical paragraph is separated by a blank line so report.py can split them.
    """
    bh          = raw.loc["Buy & Hold"]
    active_raw  = raw.drop(index="Buy & Hold")
    tf          = raw.loc["Trend Following"]
    mr          = raw.loc["Mean Reversion"]
    cus         = raw.loc["Custom Triple Confirmation"]

    # best_sharpe is always one of the three implemented strategies (not Buy & Hold)
    best_active_sharpe  = active_raw["sharpe"].idxmax()
    best_active_sortino = active_raw["sortino"].idxmax()
    best_active_return  = active_raw["total_return"].idxmax()
    worst_active_return = active_raw["total_return"].idxmin()
    best_dd             = active_raw["max_drawdown"].idxmax()   # closest to 0 → shallowest
    worst_dd            = active_raw["max_drawdown"].idxmin()   # most negative → deepest

    rf_label = f"{risk_free*100:.1f}%" if risk_free > 0 else "0% (not used)"

    paras = []

    # ── Overview ─────────────────────────────────────────────────────────────
    paras.append(
        "<b>Overview</b>\n\n"
        f"This backtest evaluates three algorithmic trading strategies applied to "
        f"{ticker} using {('live Alpaca data' if source=='alpaca' else 'synthetic price data')} "
        f"and an initial capital of $100,000. All strategies are long-only with no "
        f"leverage and no short selling, consistent with the project specification. "
        f"Signals are generated from each day's closing prices and executed at the "
        f"following day's open, eliminating any look-ahead bias. A 1 basis-point "
        f"slippage cost is applied to each trade to approximate realistic execution "
        f"costs on a commission-free platform such as Alpaca. The risk-free rate used "
        f"for Sharpe and Sortino calculations is {rf_label}. "
        f"The central research question is: <i>which strategy performs best on a "
        f"risk-adjusted basis?</i> Raw return alone is an insufficient answer because "
        f"it ignores the risk incurred to achieve that return."
    )

    # ── Strategy design rationale ────────────────────────────────────────────
    paras.append(
        "<b>Strategy Design Rationale</b>\n\n"
        "The three strategies were constructed to represent three fundamentally "
        "different market hypotheses, drawing on distinct indicator categories.\n\n"
        "<b>Trend Following</b> (Trend: MACD + ADX + SMA-50) rests on the premise "
        "that price momentum persists: once an uptrend is established, it is more "
        "likely to continue than to reverse. The ADX filter is the key quality gate — "
        "without it, MACD crossovers fire frequently in choppy, range-bound markets "
        "and produce a high volume of losing round-trips. By requiring ADX above 25 "
        "(a widely-cited 'trending' threshold), the strategy only enters when the "
        "market's directional movement is genuinely strong, accepting fewer but "
        "higher-quality entries as a trade-off.\n\n"
        "<b>Mean Reversion</b> (Momentum + Volatility: RSI + Bollinger Bands) "
        "operates on the opposite hypothesis: extreme short-term price dislocations "
        "are temporary, and prices tend to revert toward their statistical mean. The "
        "dual entry requirement — both RSI below 30 (Wilder's oversold threshold) "
        "AND a close beneath the lower Bollinger Band (more than 2σ below the 20-day "
        "mean) — ensures entries are taken only during statistically rare, multi-indicator "
        "oversold conditions. This selectivity reduces false signals significantly, "
        "though it also means the strategy may sit in cash for extended periods "
        "waiting for extreme conditions to materialise.\n\n"
        "<b>Custom Triple Confirmation</b> (Trend + Momentum + Volume: EMA + RSI + CMF) "
        "synthesises evidence from three distinct indicator categories. The EMA-50/200 "
        "golden cross establishes that the long-term structural trend is up; the RSI "
        "crossing up through 50 — while remaining below 70 — identifies a momentum "
        "reset after a pullback rather than chasing an overbought condition; and "
        "positive CMF confirms that volume-weighted buying pressure supports the move. "
        "All three conditions must align simultaneously, making this the most "
        "selective strategy, but also the one with the most rigorous multi-factor "
        "confirmation before committing capital."
    )

    # ── Absolute return analysis ─────────────────────────────────────────────
    paras.append(
        "<b>Absolute Return Analysis</b>\n\n"
        f"Over the full backtest window, Buy &amp; Hold produced a total return of "
        f"{bh['total_return']*100:.1f}% (CAGR: {bh['cagr']*100:.1f}%). "
        f"Among the active strategies, <b>{best_active_return}</b> achieved the "
        f"highest total return at {active_raw.loc[best_active_return,'total_return']*100:.1f}% "
        f"(CAGR: {active_raw.loc[best_active_return,'cagr']*100:.1f}%), followed by "
        f"Trend Following at {tf['total_return']*100:.1f}% and Custom Triple "
        f"Confirmation at {cus['total_return']*100:.1f}%. "
        f"The strategy with the lowest total return was <b>{worst_active_return}</b> "
        f"at {active_raw.loc[worst_active_return,'total_return']*100:.1f}%.\n\n"
        f"It is important not to over-interpret raw return comparisons in isolation. "
        f"Strategies that spend time in cash will systematically underperform "
        f"buy-and-hold during a sustained bull run but will also avoid a portion of "
        f"drawdowns during corrections. The active strategies' relative returns are "
        f"therefore highly sensitive to the specific market regime captured in the "
        f"backtest window — a five-year period that happens to include a strong "
        f"uptrend will flatter passive strategies, while a period with significant "
        f"corrections will flatter active ones."
    )

    # ── Volatility ───────────────────────────────────────────────────────────
    paras.append(
        "<b>Volatility Analysis</b>\n\n"
        f"Annualised volatility measures how much the portfolio's daily returns "
        f"fluctuate. Buy &amp; Hold ran at {bh['volatility']*100:.1f}% annualised "
        f"volatility — reflecting full exposure to {ticker}'s daily price moves at "
        f"all times. The active strategies posted lower volatility figures: "
        f"Trend Following {tf['volatility']*100:.1f}%, Mean Reversion "
        f"{mr['volatility']*100:.1f}%, and Custom Triple Confirmation "
        f"{cus['volatility']*100:.1f}%. "
        f"The lower active-strategy volatility is largely mechanical: any day the "
        f"strategy is in cash contributes a 0% daily return rather than the stock's "
        f"actual return, compressing the standard deviation of the return series. "
        f"This has an important implication: lower volatility does not necessarily "
        f"mean lower risk in a practical sense — an active strategy sitting in cash "
        f"while the market rallies hard faces 'opportunity risk', which annualised "
        f"volatility does not capture."
    )

    # ── Risk-adjusted metrics ─────────────────────────────────────────────────
    paras.append(
        "<b>Risk-Adjusted Performance: Sharpe &amp; Sortino Ratios</b>\n\n"
        f"The Sharpe ratio — annualised excess return divided by total annualised "
        f"volatility — is the primary risk-adjusted performance measure used to "
        f"compare the three implemented strategies. Among the three, "
        f"<b>{best_active_sharpe}</b> achieved the highest Sharpe of "
        f"{active_raw.loc[best_active_sharpe,'sharpe']:.2f}, followed by "
        f"{[n for n in active_raw.index if n != best_active_sharpe][0]} "
        f"({active_raw.loc[[n for n in active_raw.index if n != best_active_sharpe][0],'sharpe']:.2f}) "
        f"and {[n for n in active_raw.index if n != best_active_sharpe][1]} "
        f"({active_raw.loc[[n for n in active_raw.index if n != best_active_sharpe][1],'sharpe']:.2f}). "
        f"For reference, Buy &amp; Hold posted a Sharpe of {bh['sharpe']:.2f} over the same period.\n\n"
        f"The Sortino ratio refines Sharpe by penalising only downside volatility "
        f"(negative return days) rather than all volatility. A strategy that is "
        f"volatile on the upside — large winning days — is not penalised by Sortino. "
        f"Mean Reversion posted a Sortino of {mr['sortino']:.2f}, Trend Following "
        f"{tf['sortino']:.2f}, and Custom Triple Confirmation "
        f"{cus['sortino']:.2f}. "
        f"Comparing Sharpe and Sortino for the same strategy is informative: a "
        f"Sortino ratio that is meaningfully higher than Sharpe suggests that the "
        f"strategy's volatility is predominantly on winning days (desirable), while "
        f"a Sortino close to or below Sharpe suggests losses are disproportionately "
        f"large."
    )

    # ── Drawdown analysis ─────────────────────────────────────────────────────
    paras.append(
        "<b>Drawdown &amp; Capital Preservation</b>\n\n"
        f"Maximum drawdown (MDD) measures the largest peak-to-trough decline an "
        f"investor would have experienced had they held through it — a critical "
        f"real-world metric because deep drawdowns trigger forced liquidations, "
        f"redemptions, and behavioural panic-selling that permanently lock in losses. "
        f"<b>{best_dd}</b> had the shallowest MDD at "
        f"{raw.loc[best_dd,'max_drawdown']*100:.1f}%, while <b>{worst_dd}</b> "
        f"suffered the deepest at {raw.loc[worst_dd,'max_drawdown']*100:.1f}%.\n\n"
        f"Buy &amp; Hold's MDD of {bh['max_drawdown']*100:.1f}% illustrates the "
        f"hidden cost of full passive exposure: every correction is absorbed entirely "
        f"with no defence. The active strategies reduce this by moving to cash when "
        f"their exit signals fire — but the drawdown charts also reveal that this "
        f"protection is imperfect. Trend Following, for example, can remain invested "
        f"during the early stages of a trend reversal before MACD exits, accumulating "
        f"paper losses before the exit fires. Mean Reversion's shallow MDD partly "
        f"reflects its low trade count: with fewer positions held over the period, "
        f"there are simply fewer windows of exposure to a significant downturn."
    )

    # ── Win rate & trade stats ────────────────────────────────────────────────
    paras.append(
        "<b>Win Rate &amp; Trade Frequency</b>\n\n"
        f"Win rate is the proportion of closed round-trip trades (buy → sell) that "
        f"ended profitably. It is a useful but incomplete metric: a strategy with a "
        f"40% win rate can still be net profitable if its average winning trade is "
        f"significantly larger than its average losing trade (a high profit factor). "
        f"Conversely, a 90% win rate with enormous occasional losses can be "
        f"ruinous (the 'picking up nickels in front of a steamroller' problem).\n\n"
        f"Mean Reversion achieved a win rate of {mr['win_rate']*100:.0f}% across "
        f"{int(mr['num_trades'])} trades — the selectivity of its dual-confirmation "
        f"entry (RSI<30 AND below lower Bollinger Band) means it only fires in extreme "
        f"conditions where rebounds are historically reliable. Trend Following won "
        f"{tf['win_rate']*100:.0f}% of its {int(tf['num_trades'])} trades; its lower "
        f"win rate is partly structural: trend-following strategies typically have "
        f"many small losses from false starts but a smaller number of large winning "
        f"trades that make the strategy profitable in aggregate. Custom Triple "
        f"Confirmation won {cus['win_rate']*100:.0f}% of its {int(cus['num_trades'])} "
        f"trades."
    )

    # ── Answer to the central question ───────────────────────────────────────
    paras.append(
        "<b>Answer: Which Strategy Performs Best on a Risk-Adjusted Basis?</b>\n\n"
        f"To directly answer the assignment's central question — which of the three "
        f"implemented strategies performs best on a risk-adjusted basis — the answer "
        f"is <b>{best_active_sharpe}</b>, with the highest Sharpe ratio of "
        f"{active_raw.loc[best_active_sharpe,'sharpe']:.2f} and the highest Sortino "
        f"ratio of {active_raw.loc[best_active_sortino,'sortino']:.2f} among the "
        f"three strategies. Buy &amp; Hold is excluded from this comparison because "
        f"it is the passive benchmark, not an active strategy — the assignment asks "
        f"which <i>strategy</i> (Trend Following, Mean Reversion, or Custom Triple "
        f"Confirmation) is superior on a risk-adjusted basis.\n\n"
        f"It is worth asking why the winner achieves a superior Sharpe. The Sharpe "
        f"ratio rewards strategies that generate consistent excess return without "
        f"excessive swings in either direction. A strategy in cash earns 0% return "
        f"on flat days, which suppresses portfolio volatility but also reduces the "
        f"mean return. The winning strategy strikes the best balance between these "
        f"competing forces over this specific sample period. Whether that balance "
        f"generalises to other periods or tickers requires out-of-sample testing."
    )

    # ── Limitations and future work ──────────────────────────────────────────
    paras.append(
        "<b>Limitations &amp; Future Work</b>\n\n"
        "Several important caveats apply to these results:\n\n"
        "<b>1. In-sample parameters:</b> All indicator thresholds (RSI 30/70, "
        "ADX 25, EMA 50/200, CMF 0) were set a priori from conventional technical "
        "analysis practice. In-sample optimisation would almost certainly improve "
        "reported metrics but introduces overfitting — the optimised parameters "
        "would be tuned to the noise of this specific data window and unlikely to "
        "generalise.\n\n"
        "<b>2. Single-ticker, single-window:</b> All conclusions are drawn from one "
        "security over one five-year period. A strategy that performs well on AAPL "
        "from 2019–2024 may fail on SPY, NVDA, or a different five-year window. "
        "Robust strategy validation requires testing across many tickers and multiple "
        "non-overlapping windows.\n\n"
        "<b>3. Simplified cost model:</b> Slippage is modelled as a flat 1 bp per "
        "trade. Real slippage is higher during volatile or illiquid periods, and may "
        "be lower during calm periods for a liquid large-cap. A more realistic model "
        "would scale slippage with ATR or bid-ask spread.\n\n"
        "<b>4. Long-only constraint:</b> The mean-reversion strategy cannot short "
        "overbought conditions (RSI > 70), which would likely improve both its total "
        "return and its Sharpe. The long-only constraint is imposed by the assignment "
        "specification, not by any inherent strategy limitation.\n\n"
        "<b>5. Binary position sizing:</b> All strategies are either 100% invested "
        "or 100% in cash. Introducing position-sizing rules (e.g., scaling size with "
        "ATR-based risk, or Kelly fraction) could significantly improve risk-adjusted "
        "returns by deploying less capital when confidence is lower.\n\n"
        "Extensions worth exploring: walk-forward parameter optimisation; multi-asset "
        "diversification across sectors; transaction-cost sensitivity analysis; adding "
        "a volatility-regime filter (e.g., VIX-based) to suppress signals in "
        "high-volatility environments; and incorporating position sizing beyond the "
        "binary all-in/all-out framework used here."
    )

    # ── Conclusion ───────────────────────────────────────────────────────────
    paras.append(
        "<b>Conclusion</b>\n\n"
        f"This project built a complete, modular backtesting platform from scratch "
        f"that downloads market data from Alpaca, computes 11 technical indicators "
        f"across all four required categories, runs three rigorously designed trading "
        f"strategies plus a Buy &amp; Hold benchmark, and evaluates each on seven "
        f"risk and performance metrics.\n\n"
        f"The key finding is that on a risk-adjusted basis (Sharpe ratio), "
        f"<b>{best_active_sharpe}</b> was the strongest active strategy over this "
        f"backtest window. Its combination of {'controlled drawdowns and higher win rate' if best_active_sharpe == 'Mean Reversion' else 'momentum persistence and directional consistency'} "
        f"delivers the best return per unit of risk among the three active approaches. "
        f"However, as discussed in the limitations section, no single backtest result "
        f"on a single security over a single time window should be interpreted as a "
        f"definitive ranking — the true test of any strategy is its performance on "
        f"data it has never seen."
    )

    if source == "synthetic":
        paras.append(
            "<i>Data note: this run used the synthetic GBM fallback because Alpaca "
            "API credentials were not detected in the environment. The numbers above "
            "are illustrative of the pipeline's behaviour and should not be interpreted "
            "as actual market performance. To reproduce with live market data, ensure "
            "APCA_API_KEY_ID and APCA_API_SECRET_KEY are set in a .env file (or as "
            "environment variables) and re-run.</i>"
        )

    return "\n\n".join(paras)


# ── Main pipeline ─────────────────────────────────────────────────────────────

def run(ticker: str, years: int, risk_free: float, cost_bps: float) -> None:
    print(f"\n=== Backtesting {ticker} over {years}y ===")

    # 1. Data
    df = data_loader.load_data(ticker, years=years)
    source = df.attrs.get("source", "unknown")
    print(f"Loaded {len(df)} daily bars  (source: {source}, "
          f"{df.index[0].date()} to {df.index[-1].date()})")

    # 2. Indicators
    enriched = indicators.add_all_indicators(df)

    # 3. Strategies + 4. Backtest
    results = {}
    results["Buy & Hold"] = backtest.buy_and_hold(enriched)
    for name, fn in strategies.STRATEGIES.items():
        position = fn(enriched)
        results[name] = backtest.run_backtest(
            enriched, position, name=name, cost_bps=cost_bps
        )
        n_trades = int((results[name].trades["side"] == "BUY").sum()) \
            if not results[name].trades.empty else 0
        print(f"  {name:<30} entries: {n_trades}")

    # 5. Metrics
    raw = metrics.metrics_table(results, risk_free=risk_free)
    fmt = metrics.format_metrics_table(raw)
    print("\nPerformance:\n", fmt.to_string())

    REPORT.mkdir(exist_ok=True)
    raw.to_csv(REPORT / f"performance_{ticker}.csv")

    # Additional metrics
    ps            = metrics.price_stats(enriched)
    yearly_ret    = metrics.yearly_returns_table(results)
    trade_stats   = {
        name: metrics.trade_statistics(res)
        for name, res in results.items()
        if name != "Buy & Hold"
    }

    # 6. Charts
    CHARTS.mkdir(exist_ok=True)
    chart_paths = {
        "equity":   visualize.equity_curve(results, ticker, CHARTS),
        "drawdown": visualize.drawdown_chart(results, ticker, CHARTS),
        "price":    {},
    }
    for name in strategies.STRATEGIES:
        chart_paths["price"][name] = visualize.price_chart(
            enriched, results[name], ticker, CHARTS
        )

    # 7. Report
    discussion = build_discussion(ticker, raw, fmt, source, risk_free)
    date_range = f"{enriched.index[0].date()} to {enriched.index[-1].date()}"
    pdf = report.build_report(
        ticker=ticker,
        years=years,
        data_source=(
            "Alpaca Historical Market Data API (split & dividend adjusted)"
            if source == "alpaca" else "Synthetic GBM (deterministic fallback)"
        ),
        fmt_table=fmt,
        raw_table=raw,
        chart_paths=chart_paths,
        out_path=REPORT / "final_report.pdf",
        discussion=discussion,
        num_bars=len(enriched),
        date_range=date_range,
        price_stats=ps,
        yearly_returns=yearly_ret,
        trade_stats=trade_stats,
        risk_free=risk_free,
    )
    print(f"\nReport  : {pdf}")
    print(f"Charts  : {CHARTS}")
    print(f"CSV     : {REPORT / f'performance_{ticker}.csv'}")


def main():
    p = argparse.ArgumentParser(description="Alpaca strategy backtester")
    p.add_argument("--ticker",    default="AAPL",
                   help="Symbol, e.g. AAPL MSFT SPY QQQ NVDA")
    p.add_argument("--years",     type=int,   default=5,
                   help="Lookback in years (>=5)")
    p.add_argument("--risk-free", type=float, default=0.0,
                   help="Annual risk-free rate for Sharpe/Sortino, e.g. 0.04")
    p.add_argument("--cost-bps",  type=float, default=1.0,
                   help="Per-trade slippage in basis points")
    args = p.parse_args()
    run(args.ticker.upper(), max(args.years, 1), args.risk_free, args.cost_bps)


if __name__ == "__main__":
    main()
