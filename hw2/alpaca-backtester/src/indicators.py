"""
indicators.py
=============
Pure-pandas/numpy implementations of common technical indicators.

No third-party TA library is required so the math is fully transparent and
auditable. Every function takes an OHLCV DataFrame (columns: open, high, low,
close, volume) and returns either a Series or a DataFrame that can be assigned
back onto the price frame.

Categories implemented
----------------------
Trend       : SMA, EMA, MACD, ADX
Momentum    : RSI, Stochastic Oscillator, Williams %R
Volatility  : Bollinger Bands, ATR
Volume      : OBV, Chaikin Money Flow (CMF)
"""

from __future__ import annotations

import numpy as np
import pandas as pd


# --------------------------------------------------------------------------- #
# Trend
# --------------------------------------------------------------------------- #
def sma(series: pd.Series, window: int = 20) -> pd.Series:
    """Simple Moving Average."""
    return series.rolling(window=window, min_periods=window).mean()


def ema(series: pd.Series, window: int = 20) -> pd.Series:
    """Exponential Moving Average."""
    return series.ewm(span=window, adjust=False).mean()


def macd(
    series: pd.Series,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> pd.DataFrame:
    """
    Moving Average Convergence Divergence.

    Returns columns: macd, macd_signal, macd_hist.
    """
    fast_ema = ema(series, fast)
    slow_ema = ema(series, slow)
    macd_line = fast_ema - slow_ema
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    hist = macd_line - signal_line
    return pd.DataFrame(
        {"macd": macd_line, "macd_signal": signal_line, "macd_hist": hist}
    )


def adx(df: pd.DataFrame, window: int = 14) -> pd.DataFrame:
    """
    Average Directional Index (Wilder).

    Returns columns: adx, plus_di, minus_di.
    Measures *strength* of a trend (not direction). ADX > 25 is commonly read
    as a strong trend.
    """
    high, low, close = df["high"], df["low"], df["close"]

    up_move = high.diff()
    down_move = -low.diff()

    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)
    plus_dm = pd.Series(plus_dm, index=df.index)
    minus_dm = pd.Series(minus_dm, index=df.index)

    # True Range
    prev_close = close.shift(1)
    tr = pd.concat(
        [high - low, (high - prev_close).abs(), (low - prev_close).abs()], axis=1
    ).max(axis=1)

    # Wilder smoothing == EMA with alpha = 1/window
    atr_ = tr.ewm(alpha=1 / window, adjust=False).mean()
    plus_di = 100 * plus_dm.ewm(alpha=1 / window, adjust=False).mean() / atr_
    minus_di = 100 * minus_dm.ewm(alpha=1 / window, adjust=False).mean() / atr_

    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    adx_ = dx.ewm(alpha=1 / window, adjust=False).mean()

    return pd.DataFrame({"adx": adx_, "plus_di": plus_di, "minus_di": minus_di})


# --------------------------------------------------------------------------- #
# Momentum
# --------------------------------------------------------------------------- #
def rsi(series: pd.Series, window: int = 14) -> pd.Series:
    """Relative Strength Index (Wilder smoothing)."""
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / window, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / window, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def stochastic(df: pd.DataFrame, k: int = 14, d: int = 3) -> pd.DataFrame:
    """
    Stochastic Oscillator.

    Returns columns: stoch_k, stoch_d (both 0-100).
    """
    low_min = df["low"].rolling(window=k, min_periods=k).min()
    high_max = df["high"].rolling(window=k, min_periods=k).max()
    percent_k = 100 * (df["close"] - low_min) / (high_max - low_min).replace(0, np.nan)
    percent_d = percent_k.rolling(window=d, min_periods=d).mean()
    return pd.DataFrame({"stoch_k": percent_k, "stoch_d": percent_d})


def williams_r(df: pd.DataFrame, window: int = 14) -> pd.Series:
    """Williams %R (ranges from -100 to 0)."""
    high_max = df["high"].rolling(window=window, min_periods=window).max()
    low_min = df["low"].rolling(window=window, min_periods=window).min()
    return -100 * (high_max - df["close"]) / (high_max - low_min).replace(0, np.nan)


# --------------------------------------------------------------------------- #
# Volatility
# --------------------------------------------------------------------------- #
def bollinger_bands(
    series: pd.Series, window: int = 20, num_std: float = 2.0
) -> pd.DataFrame:
    """
    Bollinger Bands.

    Returns columns: bb_mid, bb_upper, bb_lower, bb_pctb, bb_width.
    """
    mid = sma(series, window)
    std = series.rolling(window=window, min_periods=window).std()
    upper = mid + num_std * std
    lower = mid - num_std * std
    pctb = (series - lower) / (upper - lower).replace(0, np.nan)
    width = (upper - lower) / mid
    return pd.DataFrame(
        {
            "bb_mid": mid,
            "bb_upper": upper,
            "bb_lower": lower,
            "bb_pctb": pctb,
            "bb_width": width,
        }
    )


def atr(df: pd.DataFrame, window: int = 14) -> pd.Series:
    """Average True Range (Wilder)."""
    high, low, close = df["high"], df["low"], df["close"]
    prev_close = close.shift(1)
    tr = pd.concat(
        [high - low, (high - prev_close).abs(), (low - prev_close).abs()], axis=1
    ).max(axis=1)
    return tr.ewm(alpha=1 / window, adjust=False).mean()


# --------------------------------------------------------------------------- #
# Volume
# --------------------------------------------------------------------------- #
def obv(df: pd.DataFrame) -> pd.Series:
    """On-Balance Volume."""
    direction = np.sign(df["close"].diff()).fillna(0.0)
    return (direction * df["volume"]).cumsum()


def cmf(df: pd.DataFrame, window: int = 20) -> pd.Series:
    """Chaikin Money Flow."""
    high, low, close, vol = df["high"], df["low"], df["close"], df["volume"]
    hl_range = (high - low).replace(0, np.nan)
    mf_mult = ((close - low) - (high - close)) / hl_range
    mf_vol = mf_mult * vol
    return (
        mf_vol.rolling(window=window, min_periods=window).sum()
        / vol.rolling(window=window, min_periods=window).sum()
    )


# --------------------------------------------------------------------------- #
# Convenience: attach a standard indicator set to a price frame
# --------------------------------------------------------------------------- #
def add_all_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """
    Return a copy of ``df`` with the full indicator set attached.

    This is what the strategies and price chart consume.
    """
    out = df.copy()
    close = out["close"]

    # Trend
    out["sma_20"] = sma(close, 20)
    out["sma_50"] = sma(close, 50)
    out["sma_200"] = sma(close, 200)
    out["ema_12"] = ema(close, 12)
    out["ema_26"] = ema(close, 26)
    out["ema_50"] = ema(close, 50)
    out["ema_200"] = ema(close, 200)
    out = out.join(macd(close))
    out = out.join(adx(out))

    # Momentum
    out["rsi"] = rsi(close, 14)
    out = out.join(stochastic(out))
    out["williams_r"] = williams_r(out)

    # Volatility
    out = out.join(bollinger_bands(close))
    out["atr"] = atr(out)

    # Volume
    out["obv"] = obv(out)
    out["cmf"] = cmf(out)

    return out
