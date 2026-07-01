"""
data_loader.py
==============
Fetch historical daily OHLCV bars.

Primary source : Alpaca Historical Market Data API (via the official
                 ``alpaca-py`` SDK).
Fallback       : a deterministic synthetic generator so the full pipeline is
                 runnable without credentials or network access.

Credential lookup order (first match wins):
    1. Environment variables: ALPACA_API_KEY  + ALPACA_SECRET_KEY
    2. Environment variables: APCA_API_KEY_ID + APCA_API_SECRET_KEY   (Alpaca legacy)
    3. A .env file anywhere in the directory tree above this file
       (loaded automatically via python-dotenv)

The free Alpaca data plan (IEX feed) is sufficient for daily bars.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

# ── Auto-load .env from the project tree ──────────────────────────────────────
try:
    from dotenv import find_dotenv, load_dotenv

    # Search upward from this file's location; also try a few sibling paths.
    _dotenv_path = find_dotenv(usecwd=False, raise_error_if_not_found=False)

    # If not found, try common relative locations (class folder, hw subdirs).
    if not _dotenv_path:
        _here = Path(__file__).resolve()
        _candidates = [
            _here.parents[1] / ".env",          # alpaca-backtester/
            _here.parents[2] / ".env",           # hw2/
            _here.parents[3] / ".env",           # QUANT FINANCE CLASS/
            _here.parents[3] / "my-market-terminal" / "hw2" / ".env",
        ]
        for _c in _candidates:
            if _c.exists():
                _dotenv_path = str(_c)
                break

    if _dotenv_path:
        load_dotenv(_dotenv_path, override=False)
        print(f"[data_loader] Loaded .env from {_dotenv_path}")
except ImportError:
    pass  # python-dotenv not installed; rely on env vars already being set

CACHE_DIR = Path(__file__).resolve().parent.parent / "data"
CACHE_DIR.mkdir(exist_ok=True)

OHLCV_COLS = ["open", "high", "low", "close", "volume"]


# ── Credential resolution ─────────────────────────────────────────────────────
def _get_credentials() -> tuple[str | None, str | None]:
    """Return (api_key, secret_key), trying both naming conventions."""
    key    = os.getenv("ALPACA_API_KEY")    or os.getenv("APCA_API_KEY_ID")
    secret = os.getenv("ALPACA_SECRET_KEY") or os.getenv("APCA_API_SECRET_KEY")
    return key, secret


# ── Public API ────────────────────────────────────────────────────────────────
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
    and df.attrs["source"] in {"alpaca", "synthetic"}.
    """
    ticker = ticker.upper().strip()
    end = end or datetime.utcnow()
    start = end - timedelta(days=int(years * 365.25) + 5)

    cache_path = CACHE_DIR / f"{ticker}_{years}y_daily.parquet"
    if use_cache and cache_path.exists():
        df = pd.read_parquet(cache_path)
        if not df.empty:
            df.attrs.setdefault("source", "alpaca")
            df.attrs.setdefault("ticker", ticker)
            return df

    df = _try_alpaca(ticker, start, end)
    source = "alpaca"

    if df is None or df.empty:
        if not allow_synthetic:
            raise RuntimeError(
                f"Could not fetch {ticker} from Alpaca and synthetic fallback "
                "is disabled. Check credentials and network access."
            )
        df = _synthetic_ohlcv(ticker, start, end)
        source = "synthetic"

    df = df[OHLCV_COLS].sort_index()
    df.attrs["ticker"] = ticker
    df.attrs["source"] = source

    if use_cache and source == "alpaca":
        df.to_parquet(cache_path)

    return df


# ── Alpaca ────────────────────────────────────────────────────────────────────
def _try_alpaca(ticker: str, start: datetime, end: datetime) -> pd.DataFrame | None:
    api_key, secret_key = _get_credentials()
    if not api_key or not secret_key:
        print("[data_loader] No Alpaca credentials found — using synthetic fallback.")
        return None

    try:
        # Windows can fail SSL cert verification due to missing root certs.
        # Monkey-patch requests to disable SSL verification (class project only).
        import ssl
        ssl._create_default_https_context = ssl._create_unverified_context
        try:
            import urllib3
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        except Exception:
            pass
        try:
            import requests as _req
            _orig_send = _req.Session.send
            def _no_verify_send(self, request, **kwargs):
                kwargs["verify"] = False
                return _orig_send(self, request, **kwargs)
            _req.Session.send = _no_verify_send
        except Exception:
            pass

        from alpaca.data.historical import StockHistoricalDataClient
        from alpaca.data.requests import StockBarsRequest
        from alpaca.data.timeframe import TimeFrame

        client = StockHistoricalDataClient(api_key, secret_key)
        # Try IEX feed first (free tier); fall back to SIP if subscription allows.
        request = StockBarsRequest(
            symbol_or_symbols=ticker,
            timeframe=TimeFrame.Day,
            start=start,
            end=end,
            adjustment="all",   # split & dividend adjusted
            feed="iex",         # IEX feed is available on the free plan
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
        df = df.rename(columns={c: c for c in ["open", "high", "low", "close", "volume"]})
        return df[OHLCV_COLS]
    except Exception as exc:
        print(f"[data_loader] Alpaca fetch failed ({exc}); using synthetic fallback.")
        return None


# ── Synthetic fallback (deterministic per-ticker) ─────────────────────────────
def _synthetic_ohlcv(ticker: str, start: datetime, end: datetime) -> pd.DataFrame:
    """
    Geometric-Brownian-motion price path with a mild regime structure so that
    trend and mean-reversion strategies both have something to work with.

    The seed uses a stable byte-level hash (not Python's randomised hash())
    so a given symbol always produces the same series.
    """
    dates = pd.bdate_range(start=start, end=end, name="date")
    n = len(dates)
    seed = int.from_bytes(ticker.encode("utf-8"), "little") % (2**32)
    rng = np.random.default_rng(seed)

    mu = 0.00035 + (seed % 7) * 1e-5       # daily drift
    sigma = 0.014 + (seed % 5) * 0.001     # daily vol
    start_price = 50 + (seed % 250)

    regime = np.cumsum(rng.normal(0, 0.00008, n))
    daily_ret = rng.normal(mu, sigma, n) + regime
    shocks = rng.random(n) < 0.01
    daily_ret[shocks] += rng.normal(0, 0.05, shocks.sum())

    close = start_price * np.exp(np.cumsum(daily_ret))
    intraday = np.abs(rng.normal(0, sigma, n)) * close
    open_ = close * (1 + rng.normal(0, sigma * 0.5, n))
    high = np.maximum(open_, close) + intraday * rng.random(n)
    low  = np.minimum(open_, close) - intraday * rng.random(n)
    volume = rng.integers(2_000_000, 30_000_000, n).astype(float)
    volume *= 1 + 3 * np.abs(daily_ret)

    return pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close, "volume": volume},
        index=dates,
    )
