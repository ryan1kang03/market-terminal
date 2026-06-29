# Technical Indicators & Strategy Backtesting with Alpaca

A self-contained backtesting platform that downloads historical market data from
**Alpaca**, computes a suite of technical indicators, runs three long-only
trading strategies against a Buy & Hold benchmark, and produces charts plus a
final PDF report answering one question:

> **Which strategy performs best on a risk-adjusted basis?**

Everything is pure Python (pandas / numpy / matplotlib / reportlab). Indicators
are implemented from scratch so the math is fully auditable — no black-box TA
dependency.

---

## Quick start

```bash
# 1. Install
pip install -r requirements.txt

# 2. (Optional but recommended) set Alpaca credentials for live data
export ALPACA_API_KEY="your_key"
export ALPACA_SECRET_KEY="your_secret"

# 3. Run the full pipeline
python main.py --ticker AAPL --years 5 --risk-free 0.04
```

Outputs land in `charts/` and `report/`:

```
charts/equity_curve.png
charts/drawdowns.png
charts/price_trend_following.png
charts/price_mean_reversion.png
charts/price_custom_triple_confirmation.png
report/final_report.pdf
report/performance_AAPL.csv
```

### No API key? It still runs.

If `ALPACA_API_KEY` / `ALPACA_SECRET_KEY` are missing, or the Alpaca endpoint is
unreachable, the loader falls back to a **deterministic synthetic price series**
(seeded per ticker) so the entire pipeline — indicators, strategies, backtest,
metrics, charts, PDF — runs end to end for demos, CI, and grading. The report
clearly labels which data source was used.

To get a real Alpaca key: create a free account at
[alpaca.markets](https://alpaca.markets), then generate API keys from the
dashboard. The free IEX data plan is sufficient for daily bars.

---

## CLI options

| Flag | Default | Meaning |
|------|---------|---------|
| `--ticker` | `AAPL` | Symbol to test (AAPL, MSFT, SPY, QQQ, NVDA, …) |
| `--years` | `5` | Lookback length in years (project requires ≥ 5) |
| `--risk-free` | `0.0` | Annual risk-free rate for Sharpe/Sortino (e.g. `0.04`) |
| `--cost-bps` | `1.0` | Per-trade slippage in basis points |

---

## Project structure

```
alpaca-backtester/
├── main.py                # CLI orchestrator: data → indicators → backtest → report
├── requirements.txt
├── README.md
├── src/
│   ├── data_loader.py     # Alpaca historical OHLCV + synthetic fallback + caching
│   ├── indicators.py      # 11 indicators across 4 categories
│   ├── strategies.py      # 3 strategies (trend / mean-reversion / custom)
│   ├── backtest.py        # Reusable long-only backtesting engine
│   ├── metrics.py         # Sharpe, Sortino, CAGR, drawdown, win rate, …
│   ├── visualize.py       # Price, equity-curve and drawdown charts
│   └── report.py          # PDF report builder (reportlab)
├── tests/
│   └── test_smoke.py      # End-to-end smoke test on synthetic data
├── charts/                # Generated PNGs
└── report/                # final_report.pdf + performance CSV
```

---

## Technical indicators (11 implemented)

| Category | Indicators |
|----------|-----------|
| **Trend** | SMA, EMA, MACD, ADX |
| **Momentum** | RSI, Stochastic Oscillator, Williams %R |
| **Volatility** | Bollinger Bands, ATR |
| **Volume** | OBV, Chaikin Money Flow (CMF) |

All are attached to the price frame in one call via
`indicators.add_all_indicators(df)`.

---

## Strategies

Each strategy emits a `1` (fully long) / `0` (cash) position. The engine shifts
the signal forward one bar and fills at the **next open** to avoid look-ahead
bias.

**Strategy 1 — Trend Following** *(Trend: MACD + ADX + SMA-50)*
- **Buy:** MACD > signal **AND** ADX > 25 **AND** close > SMA-50
- **Sell:** MACD < signal

**Strategy 2 — Mean Reversion** *(Momentum + Volatility: RSI + Bollinger Bands)*
- **Buy:** RSI < 30 **AND** close below the lower Bollinger Band
- **Sell:** RSI > 70 **OR** close above the upper Bollinger Band

**Strategy 3 — Custom "Triple Confirmation"** *(Trend + Momentum + Volume)*
Combines three indicator categories — buys pullbacks inside a confirmed uptrend:
- **Buy:** EMA-50 > EMA-200 (uptrend) **AND** RSI crosses up through 50 (and < 70)
  **AND** CMF > 0 (accumulation)
- **Sell:** close < EMA-50 **OR** RSI > 75 **OR** CMF < −0.05

**Benchmark — Buy & Hold:** buy at the first open, hold to the end.

---

## Backtesting engine

Assumptions per spec:

- Initial capital **$100,000**
- **Long-only**, **no leverage**, **no short selling** (position ∈ {0, 1})
- Signals from the close, executed at the **next open**
- Configurable slippage (`--cost-bps`, default 1 bp). Alpaca equity commissions
  are $0, so this models slippage only.

The engine tracks the daily **portfolio value**, **daily returns**, the held
**position**, and a full **trade ledger** with per-round-trip P&L and win/loss
tags.

---

## Performance metrics

| Metric | Definition |
|--------|-----------|
| **Total Return** | Final / initial − 1 |
| **CAGR** | Compound annual growth rate over the actual date span |
| **Volatility** | Annualised σ of daily returns (×√252) |
| **Sharpe** | Annualised mean excess return / σ of excess return |
| **Sortino** | Annualised mean excess return / downside deviation |
| **Max Drawdown** | Largest peak-to-trough decline in equity |
| **Win Rate** | Share of closed round-trip trades that were profitable |

---

## Using the library programmatically

```python
from src import data_loader, indicators, strategies, backtest, metrics

df = data_loader.load_data("MSFT", years=5)
enriched = indicators.add_all_indicators(df)

pos = strategies.trend_following(enriched)
res = backtest.run_backtest(enriched, pos, name="Trend Following")

print(metrics.compute_metrics(res, risk_free=0.04))
```

---

## Testing

```bash
python -m pytest tests/ -q       # or: python tests/test_smoke.py
```

The smoke test forces the synthetic data path so it needs no network or keys.

---

## Notes & caveats

- Backtests are hypothetical, exclude taxes, and assume next-open fills with a
  small slippage allowance. A single ticker is a small sample.
- For a robust conclusion, run across many tickers and time windows and check
  parameter stability (thresholds and lookbacks).
- This is an educational project, **not investment advice**.

## License

MIT (for the educational code in this repository). Market data is subject to
Alpaca's terms of service.
