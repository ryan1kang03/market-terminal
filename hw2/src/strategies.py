"""
strategies.py
=============
Each strategy is a function that consumes a DataFrame already enriched with
indicators (see indicators.add_all_indicators) and returns an integer
**position** Series:

    1 -> hold a full long position that day
    0 -> hold cash that day

The backtest engine shifts the position by one bar so that a signal generated
from a day's close is acted on at the *next* open — this avoids look-ahead bias.

Strategies are long-only (no shorting, no leverage), matching the project spec.
We use explicit entry/exit (regime) logic and forward-fill the held state so a
position persists until an exit condition flips it off.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def _state_from_entries_exits(
    index: pd.Index, entries: pd.Series, exits: pd.Series
) -> pd.Series:
    """
    Convert boolean entry/exit signals into a persistent 0/1 position.

    Once an entry fires we are long until an exit fires. Entries while already
    long are ignored; exits while already flat are ignored.
    """
    entries = entries.fillna(False).to_numpy(dtype=bool)
    exits = exits.fillna(False).to_numpy(dtype=bool)
    pos = np.zeros(len(index), dtype=int)
    holding = False
    for i in range(len(index)):
        if holding:
            if exits[i]:
                holding = False
        else:
            if entries[i]:
                holding = True
        pos[i] = 1 if holding else 0
    return pd.Series(pos, index=index, name="position")


# --------------------------------------------------------------------------- #
# Strategy 1 — Trend Following  (MACD + ADX, with an MA regime filter)
# --------------------------------------------------------------------------- #
def trend_following(df: pd.DataFrame, adx_threshold: float = 25.0) -> pd.Series:
    """
    Entry : MACD line crosses/sits above its signal line
            AND ADX > threshold (a genuinely trending market)
            AND close > 50-day SMA (only trade with the broader uptrend).
    Exit  : MACD line falls below its signal line.
    """
    macd_above = df["macd"] > df["macd_signal"]
    strong_trend = df["adx"] > adx_threshold
    above_ma = df["close"] > df["sma_50"]

    entries = macd_above & strong_trend & above_ma
    exits = df["macd"] < df["macd_signal"]

    return _state_from_entries_exits(df.index, entries, exits)


# --------------------------------------------------------------------------- #
# Strategy 2 — Mean Reversion  (RSI + Bollinger Bands)
# --------------------------------------------------------------------------- #
def mean_reversion(
    df: pd.DataFrame, rsi_low: float = 30.0, rsi_high: float = 70.0
) -> pd.Series:
    """
    Entry : RSI < rsi_low AND close below the lower Bollinger Band
            (price is statistically stretched to the downside).
    Exit  : RSI > rsi_high OR close back above the upper Bollinger Band
            (mean reversion has played out / overbought).
    """
    entries = (df["rsi"] < rsi_low) & (df["close"] < df["bb_lower"])
    exits = (df["rsi"] > rsi_high) | (df["close"] > df["bb_upper"])

    return _state_from_entries_exits(df.index, entries, exits)


# --------------------------------------------------------------------------- #
# Strategy 3 — Custom "Triple Confirmation"
#   combines TREND + MOMENTUM + VOLUME (three categories)
# --------------------------------------------------------------------------- #
def custom_triple_confirmation(df: pd.DataFrame) -> pd.Series:
    """
    A pullback-in-an-uptrend strategy requiring agreement across three
    indicator families before committing capital.

    Trend filter (Trend)      : EMA-50 > EMA-200  -> primary uptrend.
    Momentum trigger (Momentum): RSI crosses up through 50 -> momentum turning
                                 positive after a dip (not yet overbought,
                                 RSI < 70).
    Volume confirmation (Volume): CMF > 0 -> net accumulation / buying pressure.

    Entry : all three conditions true on the same bar.
    Exit  : trend breaks (close < EMA-50) OR momentum exhausts (RSI > 75)
            OR distribution sets in (CMF < -0.05).
    """
    uptrend = df["ema_50"] > df["ema_200"]
    rsi_cross_up = (df["rsi"] > 50) & (df["rsi"].shift(1) <= 50) & (df["rsi"] < 70)
    accumulation = df["cmf"] > 0

    entries = uptrend & rsi_cross_up & accumulation
    exits = (
        (df["close"] < df["ema_50"])
        | (df["rsi"] > 75)
        | (df["cmf"] < -0.05)
    )

    return _state_from_entries_exits(df.index, entries, exits)


# --------------------------------------------------------------------------- #
# Registry
# --------------------------------------------------------------------------- #
STRATEGIES = {
    "Trend Following": trend_following,
    "Mean Reversion": mean_reversion,
    "Custom Triple Confirmation": custom_triple_confirmation,
}

STRATEGY_DESCRIPTIONS = {
    "Trend Following": {
        "category": "Trend (MACD + ADX + SMA-50)",
        "entry": "MACD > signal AND ADX > 25 AND close > SMA-50",
        "exit": "MACD < signal",
    },
    "Mean Reversion": {
        "category": "Momentum + Volatility (RSI + Bollinger Bands)",
        "entry": "RSI < 30 AND close < lower Bollinger Band",
        "exit": "RSI > 70 OR close > upper Bollinger Band",
    },
    "Custom Triple Confirmation": {
        "category": "Trend + Momentum + Volume (EMA + RSI + CMF)",
        "entry": "EMA-50 > EMA-200 AND RSI crosses up through 50 (<70) AND CMF > 0",
        "exit": "close < EMA-50 OR RSI > 75 OR CMF < -0.05",
    },
}
