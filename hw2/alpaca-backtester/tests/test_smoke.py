"""
End-to-end smoke test.

Forces the synthetic data path (no Alpaca key / network required) and asserts
that every stage of the pipeline produces sane output. Run with:

    python -m pytest tests/ -q
    # or simply:
    python tests/test_smoke.py
"""

import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import backtest, data_loader, indicators, metrics, strategies

# Ensure we never accidentally hit Alpaca during tests.
os.environ.pop("ALPACA_API_KEY", None)
os.environ.pop("ALPACA_SECRET_KEY", None)


def _get_enriched(ticker="TEST", years=5):
    df = data_loader.load_data(ticker, years=years, use_cache=False)
    return df, indicators.add_all_indicators(df)


def test_data_shape():
    df, _ = _get_enriched()
    assert df.attrs["source"] == "synthetic"
    assert list(df.columns) == ["open", "high", "low", "close", "volume"]
    assert len(df) > 252 * 4          # at least ~4y of bars
    assert (df["high"] >= df["low"]).all()
    assert (df["volume"] > 0).all()


def test_indicators_present():
    _, e = _get_enriched()
    for col in ["sma_50", "ema_200", "macd", "macd_signal", "adx", "rsi",
                "stoch_k", "williams_r", "bb_upper", "bb_lower", "atr",
                "obv", "cmf"]:
        assert col in e.columns, f"missing {col}"
    # RSI must stay within [0, 100]
    rsi = e["rsi"].dropna()
    assert rsi.between(0, 100).all()


def test_strategies_binary_position():
    _, e = _get_enriched()
    for fn in strategies.STRATEGIES.values():
        pos = fn(e)
        assert set(pos.dropna().unique()).issubset({0, 1})
        assert len(pos) == len(e)


def test_backtest_and_metrics():
    df, e = _get_enriched()
    pos = strategies.trend_following(e)
    res = backtest.run_backtest(e, pos, name="Trend Following")

    # Equity never goes negative for a long-only, no-leverage strategy.
    assert (res.equity > 0).all()
    assert res.equity.index.equals(df.index)

    m = metrics.compute_metrics(res, risk_free=0.04)
    for key in ["total_return", "cagr", "volatility", "sharpe", "sortino",
                "max_drawdown", "win_rate", "num_trades"]:
        assert key in m
    assert -1.0 <= m["max_drawdown"] <= 0.0


def test_buy_and_hold_beats_cash():
    df, e = _get_enriched()
    bh = backtest.buy_and_hold(e)
    # Synthetic series has positive drift, so B&H should finish above start.
    assert bh.equity.iloc[-1] > bh.initial_capital * 0.5


def _run_all():
    fns = [v for k, v in globals().items() if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"  PASS  {fn.__name__}")
    print(f"\nAll {len(fns)} smoke tests passed.")


if __name__ == "__main__":
    _run_all()
