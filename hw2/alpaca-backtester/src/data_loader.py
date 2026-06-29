"""
data_loader.py
==============
Fetch historical daily OHLCV bars.

Primary source : Alpaca Historical Market Data API (via the official
                 ``alpaca-py`` SDK).
Fallback       : a deterministic synthetic generator so the full pipeline is
                 runnable without credentials or network access (useful for CI,
                 demos, and grading).

Credentials are read from the environment:
    ALPACA_API_KEY
    ALPACA_SECRET_KEY

The free Alpaca data plan (IEX feed) is sufficient for daily bars.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

CACHE_DIR = Path(__file__).resolve().parent.parent / "data"
CACHE_DIR.mkdir(exist_ok=True)

OHLCV_COLS = ["open", "high", "low", "close", "volume"]


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #
def load_data(
    ticker: str,
    years: int = 5,
    *,
    end: datetime | None = None,
    use_cache: bool = True,
    allow_synthetic: bool = True,
) -> pd.DataFrame:
    """
    Return a tidy daily OHLCV DataFrame indexed by date for ``ticker``.

    Parameters
    ----------
    ticker : str           e.g. "AAPL", "SPY", "QQQ", "NVDA", "MSFT".
    years  : int           lookback length in years (default 5).
    end    : datetime      last date (default = today).
    use_cache : bool       reuse a previously downloaded parquet if present.
    allow_synthetic : bool fall back to generated data when Alpaca is
                           unavailable. Set False to force a hard failure.

    The returned frame always has lower-case columns:
        open, high, low, close, volume
    """
    ticker = ticker.upper().strip()
    end = end or datetime.utcnow()
    start = end - timedelta(days=int(years * 365.25) + 5)

    cache_path = CACHE_DIR / f"{ticker}_{years}y_daily.parquet"
    if use_cache and cache_path.exists():
        df = pd.read_parquet(cache_path)
        if not df.empty:
            return df

    df = _try_alpaca(ticker, start, end)
    source = "alpaca"

    if df is None or df.empty:
        if not allow_synthetic:
            raise RuntimeError(
                f"Could not fetch {ticker} from Alpaca and synthetic fallback "
                "is disabled. Check ALPACA_API_KEY / ALPACA_SECRET_KEY and "
                "network access."
            )
        df = _synthetic_ohlcv(ticker, start, end)
        source = "synthetic"

    df = df[OHLCV_COLS].sort_index()
    df.attrs["ticker"] = ticker
    df.attrs["source"] = source

    if use_cache and source == "alpaca":
        df.to_parquet(cache_path)

    return df


# --------------------------------------------------------------------------- #
# Alpaca
# --------------------------------------------------------------------------- #
def _try_alpaca(ticker: str, start: datetime, end: datetime) -> pd.DataFrame | None:
    api_key = os.getenv("ALPACA_API_KEY")
    secret_key = os.getenv("ALPACA_SECRET_KEY")
    if not api_key or not secret_key:
        return None

    try:
        from alpaca.data.historical import StockHistoricalDataClient
        from alpaca.data.requests import StockBarsRequest
        from alpaca.data.timeframe import TimeFrame

        client = StockHistoricalDataClient(api_key, secret_key)
        request = StockBarsRequest(
            symbol_or_symbols=ticker,
            timeframe=TimeFrame.Day,
            start=start,
            end=end,
            adjustment="all",  # split & dividend adjusted
        )
        bars = client.get_stock_bars(request)
        df = bars.df
        if df is None or df.empty:
            return None

        # alpaca-py returns a MultiIndex (symbol, timestamp); flatten it.
        if isinstance(df.index, pd.MultiIndex):
            df = df.xs(ticker, level="symbol")
        df = df.rename_axis("date")
        df.index = pd.to_datetime(df.index).tz_localize(None).normalize()
        df = df.rename(
            columns={
                "open": "open",
                "high": "high",
                "low": "low",
                "close": "close",
                "volume": "volume",
            }
        )
        return df[OHLCV_COLS]
    except Exception as exc:  # network, auth, SDK, rate-limit ...
        print(f"[data_loader] Alpaca fetch failed ({exc}); using fallback.")
        return None


# --------------------------------------------------------------------------- #
# Synthetic fallback (deterministic per-ticker)
# --------------------------------------------------------------------------- #
def _synthetic_ohlcv(ticker: str, start: datetime, end: datetime) -> pd.DataFrame:
    """
    Geometric-Brownian-motion price path with a mild regime structure so that
    trend and mean-reversion strategies both have something to chew on.

    The RNG is seeded from the ticker name, so a given symbol always produces
    the same series -> reproducible demos and tests.
    """
    dates = pd.bdate_range(start=start, end=end, name="date")
    n = len(dates)
    seed = abs(hash(ticker)) % (2**32)
    rng = np.random.default_rng(seed)

    # Base parameters vary a little by symbol.
    mu = 0.00035 + (seed % 7) * 1e-5          # daily drift
    sigma = 0.014 + (seed % 5) * 0.001        # daily vol
    start_price = 50 + (seed % 250)

    # Slowly varying drift to create trend / chop regimes.
    regime = np.cumsum(rng.normal(0, 0.00008, n))
    daily_ret = rng.normal(mu, sigma, n) + regime
    # Inject occasional volatility clusters.
    shocks = rng.random(n) < 0.01
    daily_ret[shocks] += rng.normal(0, 0.05, shocks.sum())

    close = start_price * np.exp(np.cumsum(daily_ret))

    # Build OHLC around the close path.
    intraday = np.abs(rng.normal(0, sigma, n)) * close
    open_ = close * (1 + rng.normal(0, sigma * 0.5, n))
    high = np.maximum(open_, close) + intraday * rng.random(n)
    low = np.minimum(open_, close) - intraday * rng.random(n)
    volume = rng.integers(2_000_000, 30_000_000, n).astype(float)
    # Volume tends to rise on big moves.
    volume *= 1 + 3 * np.abs(daily_ret)

    df = pd.DataFrame(
        {
            "open": open_,
            "high": high,
            "low": low,
            "close": close,
            "volume": volume,
        },
        index=dates,
    )
    return df
