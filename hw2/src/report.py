"""
report.py
=========
Build a comprehensive PDF report covering every requirement of the assignment:
  - Data summary with descriptive statistics
  - Indicator reference (all 11, with formulas)
  - Strategy descriptions and entry/exit rules
  - Backtesting methodology
  - Performance comparison table with column legend
  - Year-by-year returns table
  - Detailed trade statistics per strategy
  - All charts (equity, drawdown, price × 3)
  - Thorough multi-section discussion
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    HRFlowable,
    Image,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from .strategies import STRATEGY_DESCRIPTIONS

# ── Static reference tables ───────────────────────────────────────────────────

# 4-column table: Category | Indicator (name + code) | Parameters | Strategy usage
INDICATOR_REFERENCE = [
    ("Trend",      "Simple Moving Average (SMA)",      "windows: 20, 50, 200",    "Trend Following — SMA-50 regime filter"),
    ("Trend",      "Exponential Moving Average (EMA)", "windows: 12, 26, 50, 200","Custom Triple Confirmation — EMA-50/200 golden cross"),
    ("Trend",      "MACD & Signal Line",               "fast=12, slow=26, sig=9", "Trend Following — MACD crossover entry/exit"),
    ("Trend",      "Avg Directional Index (ADX)",      "window=14",               "Trend Following — ADX>25 trend-strength filter"),
    ("Momentum",   "Relative Strength Index (RSI)",    "window=14",               "Mean Reversion (RSI<30 entry, >70 exit) & Custom (50-cross trigger)"),
    ("Momentum",   "Stochastic Oscillator",            "k=14, d=3",               "Computed — available for custom signals"),
    ("Momentum",   "Williams %R",                      "window=14",               "Computed — available for custom signals"),
    ("Volatility", "Bollinger Bands",                  "window=20, 2 std dev",    "Mean Reversion — lower/upper band entry/exit"),
    ("Volatility", "Avg True Range (ATR)",             "window=14",               "Computed — available for stop-loss sizing"),
    ("Volume",     "On-Balance Volume (OBV)",          "cumulative",              "Computed — available for volume trend confirmation"),
    ("Volume",     "Chaikin Money Flow (CMF)",         "window=20",               "Custom Triple Confirmation — CMF>0 accumulation filter"),
]

# Formulas shown as a separate text block below the table
INDICATOR_FORMULAS = [
    ("SMA",            "SMA(n) = (1/n) x sum of last n closes"),
    ("EMA",            "EMA(t) = alpha x close(t) + (1-alpha) x EMA(t-1),   alpha = 2/(n+1)"),
    ("MACD",           "MACD = EMA(12) - EMA(26);   Signal = EMA(9) of MACD;   Hist = MACD - Signal"),
    ("ADX",            "ADX = Wilder-smoothed average of |+DI - -DI| / (+DI + -DI) x 100"),
    ("RSI",            "RSI = 100 - 100 / (1 + AvgGain / AvgLoss)   [Wilder smoothing, 14 periods]"),
    ("Stochastic",     "%K = 100 x (close - low_14) / (high_14 - low_14);   %D = SMA(%K, 3)"),
    ("Williams %R",    "%R = -100 x (high_14 - close) / (high_14 - low_14)"),
    ("Bollinger Bands","Upper/Lower = SMA(20) +/- 2 x rolling std dev(20)"),
    ("ATR",            "ATR = Wilder-EMA of True Range = max(H-L, |H-prev_C|, |L-prev_C|)"),
    ("OBV",            "OBV(t) = OBV(t-1) + sign(delta_Close) x Volume"),
    ("CMF",            "CMF = sum(MFV, 20) / sum(Volume, 20);   MFV = ((C-L)-(H-C))/(H-L) x Volume"),
]

PRICE_CHART_CAPTIONS = {
    "Trend Following": (
        "price with SMA-50 (blue) and SMA-200 (orange) trend filters, "
        "Bollinger Bands (shaded). "
        "Green ▲ = BUY (MACD crosses above signal AND ADX>25 AND close>SMA-50). "
        "Red ▼ = SELL (MACD crosses below signal). "
        "RSI(14) subplot below."
    ),
    "Mean Reversion": (
        "price with Bollinger Bands (±2σ, shaded). "
        "Green ▲ = BUY (RSI<30 AND close below lower band — extreme oversold). "
        "Red ▼ = SELL (RSI>70 OR close above upper band — mean reversion complete). "
        "RSI(14) subplot with 30/70 reference lines below."
    ),
    "Custom Triple Confirmation": (
        "price with EMA-50 (blue) and EMA-200 (orange) golden-cross filter, "
        "Bollinger Bands (shaded). "
        "Green ▲ = BUY (EMA-50>EMA-200 AND RSI crosses up through 50 and <70 AND CMF>0). "
        "Red ▼ = SELL (close<EMA-50 OR RSI>75 OR CMF<−0.05). "
        "RSI(14) subplot below."
    ),
}

METRIC_LEGEND = [
    ("Total Return",  "Cumulative % gain/loss: (final − initial) / initial"),
    ("CAGR",          "Compound Annual Growth Rate over the actual date span"),
    ("Volatility",    "Annualised standard deviation of daily returns (σ × √252)"),
    ("Sharpe",        "Annualised excess return per unit of total volatility; uses the user-supplied risk-free rate"),
    ("Sortino",       "Like Sharpe but penalises downside volatility only — a higher ratio signals that volatility is skewed to the upside (winning days)"),
    ("Max Drawdown",  "Largest peak-to-trough decline in portfolio value; measures worst-case capital destruction"),
    ("Win Rate",      "Fraction of closed round-trip trades (buy → sell) that were profitable"),
    ("# Trades",      "Total completed round-trip trades over the full backtest window"),
]


# ── Style helpers ─────────────────────────────────────────────────────────────

def _styles():
    s = getSampleStyleSheet()
    s.add(ParagraphStyle("Body2",     parent=s["BodyText"],  fontSize=9.5, leading=14))
    s.add(ParagraphStyle("Body2Ind",  parent=s["BodyText"],  fontSize=9.5, leading=14, leftIndent=12))
    s.add(ParagraphStyle("Small",     parent=s["BodyText"],  fontSize=8,   leading=11,
                         textColor=colors.HexColor("#555555")))
    s.add(ParagraphStyle("H2b",       parent=s["Heading2"],  spaceBefore=12, spaceAfter=4))
    s.add(ParagraphStyle("H3b",       parent=s["Heading3"],  spaceBefore=8,  spaceAfter=3, fontSize=10))
    s.add(ParagraphStyle("Caption",   parent=s["BodyText"],  fontSize=8, alignment=1,
                         textColor=colors.HexColor("#666666")))
    s.add(ParagraphStyle("TableNote", parent=s["BodyText"],  fontSize=7.5, leading=11,
                         textColor=colors.HexColor("#555555")))
    s.add(ParagraphStyle("BulletItem", parent=s["BodyText"], fontSize=9.5, leading=14,
                         leftIndent=14, bulletIndent=4))
    return s


def _tbl_style(header_color="#1f2937", col_widths=None):
    return TableStyle([
        ("BACKGROUND",     (0, 0), (-1, 0),  colors.HexColor(header_color)),
        ("TEXTCOLOR",      (0, 0), (-1, 0),  colors.white),
        ("FONTNAME",       (0, 0), (-1, 0),  "Helvetica-Bold"),
        ("FONTSIZE",       (0, 0), (-1, -1), 8),
        ("ALIGN",          (1, 0), (-1, -1), "CENTER"),
        ("ALIGN",          (0, 0), (0,  -1), "LEFT"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f3f4f6")]),
        ("GRID",           (0, 0), (-1, -1), 0.4, colors.HexColor("#d1d5db")),
        ("VALIGN",         (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING",     (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING",  (0, 0), (-1, -1), 4),
    ])


def _hr(story):
    story.append(Spacer(1, 4))
    story.append(HRFlowable(width="100%", thickness=0.5,
                            color=colors.HexColor("#d1d5db")))
    story.append(Spacer(1, 4))


def _img(path, width=17):
    from PIL import Image as PILImage
    with PILImage.open(path) as im:
        w, h = im.size
    target_w = width * cm
    target_h = target_w * h / w
    return Image(str(path), width=target_w, height=target_h)


def _pct(v, decimals=1):
    if pd.isna(v):
        return "n/a"
    return f"{v*100:.{decimals}f}%"


def _ratio(v, decimals=2):
    if pd.isna(v) or np.isinf(v):
        return "n/a" if pd.isna(v) else "∞"
    return f"{v:.{decimals}f}"


# ── Main builder ──────────────────────────────────────────────────────────────

def build_report(
    *,
    ticker: str,
    years: int,
    data_source: str,
    fmt_table: pd.DataFrame,
    raw_table: pd.DataFrame,
    chart_paths: dict,
    out_path: Path,
    discussion: str,
    num_bars: int = 0,
    date_range: str = "",
    price_stats: dict | None = None,
    yearly_returns: pd.DataFrame | None = None,
    trade_stats: dict | None = None,
    risk_free: float = 0.0,
) -> Path:
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    s = _styles()
    story = []

    # ═══════════════════════════════════════════════════════════════════════════
    # COVER / TITLE BLOCK
    # ═══════════════════════════════════════════════════════════════════════════
    story.append(Paragraph("Technical Indicators &amp; Strategy Backtesting", s["Title"]))
    story.append(Paragraph(
        f"Risk-adjusted comparison of three algorithmic trading strategies on "
        f"<b>{ticker}</b> using historical market data from Alpaca",
        s["Heading3"]))
    story.append(Spacer(1, 6))

    meta_parts = [
        f"Ticker: <b>{ticker}</b>",
        f"Lookback: {years} years",
        f"Data: {data_source}",
    ]
    if date_range:
        meta_parts.append(f"Period: {date_range}")
    if num_bars:
        meta_parts.append(f"{num_bars:,} daily bars")
    meta_parts.append(f"Generated: {datetime.utcnow():%Y-%m-%d %H:%M} UTC")
    story.append(Paragraph(" &nbsp;·&nbsp; ".join(meta_parts), s["Small"]))
    story.append(Spacer(1, 6))
    story.append(Paragraph(
        "Initial capital <b>$100,000</b> &nbsp;·&nbsp; "
        "Long-only, no leverage, no short selling &nbsp;·&nbsp; "
        "Signals on daily close, executed at next open &nbsp;·&nbsp; "
        f"1 bp slippage per trade &nbsp;·&nbsp; "
        f"Risk-free rate: {risk_free*100:.1f}% p.a.",
        s["Small"]))
    _hr(story)
    story.append(Spacer(1, 4))

    # ═══════════════════════════════════════════════════════════════════════════
    # SECTION 1 — DATA SUMMARY
    # ═══════════════════════════════════════════════════════════════════════════
    story.append(Paragraph("1. Data", s["H2b"]))
    story.append(Paragraph(
        f"All backtests use daily OHLCV (Open-High-Low-Close-Volume) data for "
        f"<b>{ticker}</b> downloaded from <b>{data_source}</b>. "
        f"The Alpaca SDK fetches bars adjusted for splits and dividends "
        f"(<tt>adjustment='all'</tt>), ensuring that historical returns are not "
        f"distorted by corporate actions. Data is stored locally in Parquet format "
        f"for fast re-runs without additional API calls.",
        s["Body2"]))
    story.append(Spacer(1, 5))

    if price_stats:
        ps = price_stats
        pstat_data = [
            ["Metric", "Value"],
            ["Start price",              f"${ps.get('start_price', 0):.2f}"],
            ["End price",                f"${ps.get('end_price', 0):.2f}"],
            ["Price return (full period)", _pct(ps.get('total_return'))],
            ["Annualised volatility",    _pct(ps.get('ann_vol'))],
            ["Daily return skewness",    f"{ps.get('skewness', 0):.3f}"],
            ["Daily return excess kurtosis", f"{ps.get('kurtosis', 0):.3f}"],
            ["Largest single-day gain",  _pct(ps.get('max_1d_gain'))],
            ["Largest single-day loss",  _pct(ps.get('max_1d_loss'))],
            ["Avg daily volume",         f"{ps.get('avg_daily_vol', 0):,.0f} shares"],
        ]
        pstat_tbl = Table(pstat_data, repeatRows=1, hAlign="LEFT",
                          colWidths=[7*cm, 5*cm])
        pstat_tbl.setStyle(_tbl_style("#374151"))
        story.append(pstat_tbl)
        story.append(Spacer(1, 5))

        skew = ps.get("skewness", 0)
        kurt = ps.get("kurtosis", 0)
        skew_desc = "negatively skewed (fat left tail — crashes are larger than rallies)" \
                    if skew < -0.1 else \
                    "positively skewed (large gains are more common than large losses)" \
                    if skew > 0.1 else "approximately symmetric"
        story.append(Paragraph(
            f"The return distribution is {skew_desc} with excess kurtosis of "
            f"{kurt:.2f} (positive kurtosis = fat tails relative to a normal distribution, "
            f"meaning extreme days occur more frequently than a Gaussian model predicts). "
            f"These distributional properties matter for the Sortino ratio, which "
            f"penalises fat left tails more heavily than a standard Sharpe ratio.",
            s["Body2"]))
    story.append(Spacer(1, 10))

    # ═══════════════════════════════════════════════════════════════════════════
    # SECTION 2 — TECHNICAL INDICATORS
    # ═══════════════════════════════════════════════════════════════════════════
    story.append(Paragraph("2. Technical Indicators Implemented (11 total)", s["H2b"]))
    story.append(Paragraph(
        "All 11 indicators are implemented from scratch in pure pandas/numpy — no "
        "black-box TA library dependency — so every calculation is mathematically "
        "transparent and auditable. The project requirement is a minimum of 6 "
        "indicators spanning at least two categories; this implementation covers "
        "<b>all four required categories</b>: Trend, Momentum, Volatility, and Volume.",
        s["Body2"]))
    story.append(Spacer(1, 6))

    # Wrap every cell in a Paragraph so long text word-wraps inside the column
    # instead of bleeding into the next cell.
    # Total usable width = 21cm - 2 x 1.8cm margins = 17.4cm
    cell_s = ParagraphStyle("CellWrap", parent=s["BodyText"],
                            fontSize=8, leading=11)
    hdr_s  = ParagraphStyle("CellHdr",  parent=s["BodyText"],
                            fontSize=8, leading=11,
                            textColor=colors.white, fontName="Helvetica-Bold")

    def _cell(text, style=cell_s):
        return Paragraph(str(text), style)

    ind_data = [[_cell(h, hdr_s) for h in
                 ["Category", "Indicator", "Parameters", "Strategy Usage"]]]
    for row in INDICATOR_REFERENCE:
        ind_data.append([_cell(c) for c in row])

    ind_tbl = Table(ind_data, repeatRows=1, hAlign="LEFT",
                    colWidths=[2.4*cm, 5.0*cm, 3.5*cm, 6.5*cm])
    ind_tbl.setStyle(TableStyle([
        ("BACKGROUND",     (0, 0), (-1, 0),  colors.HexColor("#374151")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f3f4f6")]),
        ("GRID",           (0, 0), (-1, -1), 0.4, colors.HexColor("#d1d5db")),
        ("VALIGN",         (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING",     (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING",  (0, 0), (-1, -1), 5),
        ("LEFTPADDING",    (0, 0), (-1, -1), 4),
        ("RIGHTPADDING",   (0, 0), (-1, -1), 4),
    ]))
    story.append(ind_tbl)
    story.append(Spacer(1, 6))

    story.append(Paragraph("<b>Indicator Formulas</b>", s["H3b"]))
    for code, formula in INDICATOR_FORMULAS:
        story.append(Paragraph(
            f"<b>{code}:</b>  {formula}",
            s["Small"]))
        story.append(Spacer(1, 2))
    story.append(Spacer(1, 4))
    story.append(Paragraph(
        "Indicators not used in primary signals (Stochastic, Williams %R, ATR, OBV) "
        "are still computed and attached to the price frame — available for "
        "custom strategy extensions.",
        s["Small"]))
    story.append(Spacer(1, 10))

    # ═══════════════════════════════════════════════════════════════════════════
    # SECTION 3 — STRATEGY DESCRIPTIONS & RULES
    # ═══════════════════════════════════════════════════════════════════════════
    story.append(Paragraph("3. Strategy Descriptions &amp; Entry/Exit Rules", s["H2b"]))

    strategy_rationale = {
        "Trend Following": (
            "Trend following (also called momentum investing) rests on the empirical "
            "observation that assets that have been rising tend to continue rising — "
            "i.e., price momentum persists across medium-term horizons. Rather than "
            "predicting reversals, this strategy identifies and joins established trends. "
            "Three conditions must all be true before buying: (1) the MACD line must "
            "sit above its signal line, confirming short-term upward price momentum; "
            "(2) the ADX must exceed 25, a widely-used threshold separating "
            "'trending' from 'sideways/choppy' markets — this filter is critical "
            "because MACD crossovers in range-bound markets produce frequent false "
            "signals; and (3) the close must be above the 50-day SMA, confirming the "
            "broader medium-term uptrend. The exit is intentionally asymmetric: a "
            "single MACD crossover below the signal line triggers the sell, so the "
            "strategy exits quickly when momentum fades."
        ),
        "Mean Reversion": (
            "Mean reversion exploits the tendency of asset prices to return toward "
            "their statistical mean after extreme dislocations. When a stock has sold "
            "off sharply enough that RSI falls below 30 (oversold) AND the close is "
            "below the lower Bollinger Band (more than 2 standard deviations below "
            "the 20-day average), the strategy interprets this as an unsustainably "
            "stretched condition likely to snap back. The dual-confirmation requirement "
            "— both RSI and Bollinger Band breach — substantially reduces false entries "
            "compared to using either signal alone, at the cost of fewer trades. "
            "The exit fires when RSI recovers above 70 (overbought, mean reversion "
            "complete) or the price recrosses the upper Bollinger Band, whichever "
            "comes first, locking in the reversion gain."
        ),
        "Custom Triple Confirmation": (
            "The Custom Triple Confirmation strategy synthesises evidence from three "
            "distinct indicator categories — Trend, Momentum, and Volume — requiring "
            "all three to agree before committing capital. This multi-factor approach "
            "is designed to avoid the weaknesses of any single indicator class: trend "
            "filters alone give late entries; momentum signals alone fire in both "
            "trending and sideways markets; volume signals alone do not give timing. "
            "Together they describe a specific, high-conviction scenario: "
            "(1) EMA-50 above EMA-200 (golden cross) — the long-term structural trend "
            "is up; (2) RSI crossing upward through 50 while below 70 — momentum is "
            "turning positive after a dip, not chasing an overbought condition; "
            "(3) CMF above zero — institutional accumulation (buying pressure) "
            "supports the move on volume. The exit is multi-legged: the position "
            "closes if the trend breaks (close below EMA-50), momentum exhausts "
            "(RSI above 75), or distribution sets in (CMF below −0.05)."
        ),
    }

    for name, d in STRATEGY_DESCRIPTIONS.items():
        story.append(Paragraph(
            f"<b>{name}</b>  <font size='8' color='#777'>[{d['category']}]</font>",
            s["H3b"]))
        story.append(Paragraph(strategy_rationale.get(name, ""), s["Body2"]))
        story.append(Spacer(1, 4))
        buy_s  = ParagraphStyle("BuyCell",  parent=s["BodyText"], fontSize=8.5,
                                leading=12, fontName="Helvetica-Bold")
        sell_s = ParagraphStyle("SellCell", parent=s["BodyText"], fontSize=8.5,
                                leading=12, fontName="Helvetica-Bold")
        rule_data = [
            [_cell("Signal", hdr_s),         _cell("Condition", hdr_s)],
            [Paragraph("ENTRY (BUY)",  buy_s), _cell(d["entry"])],
            [Paragraph("EXIT  (SELL)", sell_s), _cell(d["exit"])],
        ]
        rule_tbl = Table(rule_data, repeatRows=1, hAlign="LEFT",
                         colWidths=[2.8*cm, 14.6*cm])
        rule_tbl.setStyle(TableStyle([
            ("BACKGROUND",   (0, 0), (-1, 0), colors.HexColor("#374151")),
            ("BACKGROUND",   (0, 1), (0, 1),  colors.HexColor("#d1fae5")),
            ("BACKGROUND",   (0, 2), (0, 2),  colors.HexColor("#fee2e2")),
            ("GRID",         (0, 0), (-1, -1), 0.5, colors.HexColor("#d1d5db")),
            ("VALIGN",       (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING",   (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING",(0, 0), (-1, -1), 5),
            ("LEFTPADDING",  (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(rule_tbl)
        story.append(Spacer(1, 10))

    story.append(Paragraph(
        "<b>Benchmark — Buy &amp; Hold:</b> buy at the first available open and "
        "hold through the end of the window with no rebalancing or exits. This is "
        "the passive baseline; active strategies must justify their complexity by "
        "delivering superior risk-adjusted returns relative to simply holding.",
        s["Body2"]))
    story.append(Spacer(1, 6))

    # ═══════════════════════════════════════════════════════════════════════════
    # SECTION 4 — BACKTESTING METHODOLOGY
    # ═══════════════════════════════════════════════════════════════════════════
    story.append(Paragraph("4. Backtesting Methodology", s["H2b"]))
    story.append(Paragraph(
        "The backtesting engine is purpose-built in Python (no third-party "
        "backtesting framework) so every assumption is explicit and auditable. "
        "Key design decisions:",
        s["Body2"]))
    story.append(Spacer(1, 4))

    method_rows_raw = [
        ("Assumption", "Detail / Justification"),
        ("Initial capital",    "$100,000 (per specification)"),
        ("Position sizing",    "Binary all-in / all-out (0 = cash, 1 = fully invested). No fractional sizing."),
        ("Execution timing",   "Signal on day-t close; order filled at day t+1 open. Eliminates look-ahead bias."),
        ("Slippage / cost",    "1 basis point of notional per trade side. Alpaca equity commissions are $0; this models market-impact / spread."),
        ("Short selling",      "Not permitted (long-only per specification)."),
        ("Leverage",           "None (at most 100% of equity deployed)."),
        ("Dividends",          "Captured via Alpaca split/dividend-adjusted price series."),
        ("Data snooping",      "No in-sample parameter optimisation; all thresholds set a priori from conventional TA practice."),
        ("Trade ledger",       "Every BUY and SELL recorded with date, price, shares, cost. Round-trip P&L and win/loss annotated."),
    ]
    meth_data = [[_cell(a, hdr_s), _cell(b, hdr_s)] for a, b in method_rows_raw[:1]] + \
                [[_cell(a), _cell(b)] for a, b in method_rows_raw[1:]]
    meth_tbl = Table(meth_data, repeatRows=1, hAlign="LEFT",
                     colWidths=[4.5*cm, 12.9*cm])
    meth_tbl.setStyle(TableStyle([
        ("BACKGROUND",     (0, 0), (-1, 0),  colors.HexColor("#374151")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f3f4f6")]),
        ("GRID",           (0, 0), (-1, -1), 0.4, colors.HexColor("#d1d5db")),
        ("VALIGN",         (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING",     (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING",  (0, 0), (-1, -1), 5),
        ("LEFTPADDING",    (0, 0), (-1, -1), 4),
        ("RIGHTPADDING",   (0, 0), (-1, -1), 4),
    ]))
    story.append(meth_tbl)
    story.append(Spacer(1, 10))

    # ═══════════════════════════════════════════════════════════════════════════
    # SECTION 5 — PERFORMANCE METRICS
    # ═══════════════════════════════════════════════════════════════════════════
    story.append(Paragraph("5. Performance Metrics &amp; Results", s["H2b"]))

    # 5a. Metric definitions
    story.append(Paragraph("<b>5a. Metric Definitions</b>", s["H3b"]))
    met_data = [[_cell("Metric", hdr_s), _cell("Definition", hdr_s)]] + \
               [[_cell(m), _cell(d)] for m, d in METRIC_LEGEND]
    met_tbl = Table(met_data, repeatRows=1, hAlign="LEFT",
                    colWidths=[3.5*cm, 13.9*cm])
    met_tbl.setStyle(TableStyle([
        ("BACKGROUND",     (0, 0), (-1, 0),  colors.HexColor("#374151")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f3f4f6")]),
        ("GRID",           (0, 0), (-1, -1), 0.4, colors.HexColor("#d1d5db")),
        ("VALIGN",         (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING",     (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING",  (0, 0), (-1, -1), 5),
        ("LEFTPADDING",    (0, 0), (-1, -1), 4),
        ("RIGHTPADDING",   (0, 0), (-1, -1), 4),
    ]))
    story.append(met_tbl)
    story.append(Spacer(1, 8))

    # 5b. Main performance table
    story.append(Paragraph("<b>5b. Overall Performance Comparison</b>", s["H3b"]))
    header = ["Strategy"] + list(fmt_table.columns)
    data = [header]
    for idx, row in fmt_table.iterrows():
        data.append([idx] + [str(v) for v in row.tolist()])
    perf_tbl = Table(data, repeatRows=1, hAlign="LEFT")
    perf_tbl.setStyle(_tbl_style())
    story.append(perf_tbl)
    story.append(Spacer(1, 4))

    # Best strategy = best among the three implemented strategies, not Buy & Hold
    active_table       = raw_table.drop(index="Buy & Hold")
    best_active_sharpe = active_table["sharpe"].idxmax()
    best_active_return = active_table["total_return"].idxmax()
    story.append(Paragraph(
        f"<b>Best strategy by Sharpe (among the 3 implemented):</b> "
        f"{best_active_sharpe} ({active_table.loc[best_active_sharpe,'sharpe']:.2f})  "
        f"&nbsp;·&nbsp;  "
        f"<b>Best strategy by total return:</b> {best_active_return} "
        f"({active_table.loc[best_active_return,'total_return']*100:.1f}%)  "
        f"&nbsp;·&nbsp;  "
        f"<b>Buy &amp; Hold benchmark Sharpe:</b> "
        f"{raw_table.loc['Buy & Hold','sharpe']:.2f} (reference only)",
        s["Small"]))
    story.append(Spacer(1, 10))

    # 5c. Year-by-year returns
    if yearly_returns is not None and not yearly_returns.empty:
        story.append(Paragraph("<b>5c. Calendar-Year Returns</b>", s["H3b"]))
        story.append(Paragraph(
            "Breaking performance into calendar years reveals how each strategy "
            "behaves across different market regimes — bull runs, corrections, and "
            "sideways markets.",
            s["Body2"]))
        story.append(Spacer(1, 4))

        yr_header = ["Year"] + list(yearly_returns.columns)
        yr_data = [yr_header]
        for year, row in yearly_returns.iterrows():
            yr_row = [str(year)]
            for v in row:
                if pd.isna(v):
                    yr_row.append("n/a")
                elif v >= 0:
                    yr_row.append(f"+{v*100:.1f}%")
                else:
                    yr_row.append(f"{v*100:.1f}%")
            yr_data.append(yr_row)

        yr_tbl = Table(yr_data, repeatRows=1, hAlign="LEFT")
        base_style = _tbl_style()
        yr_tbl.setStyle(base_style)
        # Colour positive green, negative red
        for ri, row in enumerate(yr_data[1:], start=1):
            for ci, cell in enumerate(row[1:], start=1):
                if cell.startswith("+"):
                    yr_tbl.setStyle(TableStyle([
                        ("BACKGROUND", (ci, ri), (ci, ri), colors.HexColor("#d1fae5"))
                    ]))
                elif cell.startswith("-"):
                    yr_tbl.setStyle(TableStyle([
                        ("BACKGROUND", (ci, ri), (ci, ri), colors.HexColor("#fee2e2"))
                    ]))
        story.append(yr_tbl)
        story.append(Spacer(1, 10))

    # 5d. Detailed trade statistics
    if trade_stats:
        story.append(Paragraph("<b>5d. Trade-Level Statistics</b>", s["H3b"]))
        story.append(Paragraph(
            "The table below drills into per-trade performance. Profit Factor = "
            "gross winning P&amp;L / gross losing P&amp;L; a value above 1 means "
            "winning trades outweigh losers in dollar terms even if the win rate "
            "is below 50%.",
            s["Body2"]))
        story.append(Spacer(1, 4))

        ts_header = ["Strategy", "# Trades", "Win Rate", "Avg Winner",
                     "Avg Loser", "Profit Factor", "Best Trade", "Worst Trade", "Avg Hold (days)"]
        ts_data = [ts_header]
        for strat, ts in trade_stats.items():
            ts_data.append([
                strat,
                str(int(ts.get("num_trades", 0))) if not pd.isna(ts.get("num_trades", np.nan)) else "0",
                _pct(ts.get("win_rate")),
                _pct(ts.get("avg_winner_pct")),
                _pct(ts.get("avg_loser_pct")),
                _ratio(ts.get("profit_factor")),
                _pct(ts.get("best_trade_pct")),
                _pct(ts.get("worst_trade_pct")),
                f"{ts.get('avg_hold_days', np.nan):.0f}" if not pd.isna(ts.get("avg_hold_days", np.nan)) else "n/a",
            ])
        ts_tbl = Table(ts_data, repeatRows=1, hAlign="LEFT")
        ts_tbl.setStyle(_tbl_style())
        story.append(ts_tbl)
        story.append(Spacer(1, 10))

    story.append(PageBreak())

    # ═══════════════════════════════════════════════════════════════════════════
    # SECTION 6 — CHARTS
    # ═══════════════════════════════════════════════════════════════════════════
    story.append(Paragraph("6. Charts", s["H2b"]))

    # Equity curve
    story.append(Paragraph("<b>6a. Equity Curves</b>", s["H3b"]))
    story.append(Paragraph(
        "Shows the growth of a $100,000 initial investment for each strategy over "
        "the full backtest window. The dashed grey line is the Buy &amp; Hold "
        "benchmark. Periods where an active strategy's line is above Buy &amp; Hold "
        "represent outperformance; periods below represent underperformance. Time "
        "spent flat (in cash) appears as horizontal plateaus.",
        s["Body2"]))
    story.append(Spacer(1, 4))
    story.append(_img(chart_paths["equity"], width=17))
    story.append(Paragraph(
        "Figure 1. Portfolio value over time. All strategies start at $100,000.",
        s["Caption"]))
    story.append(Spacer(1, 10))

    # Drawdown
    story.append(Paragraph("<b>6b. Drawdown Comparison</b>", s["H3b"]))
    story.append(Paragraph(
        "The underwater plot shows each strategy's percentage decline from its most "
        "recent equity peak. A strategy at 0% is at a new all-time high; a strategy "
        "at −20% has lost 20% from its prior peak. Shallower and shorter drawdowns "
        "indicate superior capital preservation — a critical real-world consideration "
        "since investors may liquidate during deep drawdowns, permanently locking in "
        "losses.",
        s["Body2"]))
    story.append(Spacer(1, 4))
    story.append(_img(chart_paths["drawdown"], width=17))
    story.append(Paragraph(
        "Figure 2. Underwater plot: depth and duration of drawdowns from each "
        "strategy's prior equity peak.",
        s["Caption"]))
    story.append(PageBreak())

    # Price charts
    story.append(Paragraph("<b>6c. Price Charts with Indicators &amp; Trade Signals</b>", s["H3b"]))
    story.append(Paragraph(
        "Each chart below shows the price series with its relevant technical "
        "indicators overlaid, plus buy (▲) and sell (▼) markers at the actual "
        "execution price. The RSI subplot provides momentum context across all "
        "three strategies.",
        s["Body2"]))
    story.append(Spacer(1, 6))

    fig_n = 3
    for label, p in chart_paths.get("price", {}).items():
        story.append(_img(p, width=17))
        caption = PRICE_CHART_CAPTIONS.get(label, f"{label}: price, indicators & signals.")
        story.append(Paragraph(
            f"Figure {fig_n}. <b>{label}</b>: {caption}",
            s["Caption"]))
        story.append(Spacer(1, 10))
        fig_n += 1

    story.append(PageBreak())

    # ═══════════════════════════════════════════════════════════════════════════
    # SECTION 7 — DISCUSSION
    # ═══════════════════════════════════════════════════════════════════════════
    story.append(Paragraph("7. Discussion of Results", s["H2b"]))
    for para in discussion.strip().split("\n\n"):
        para = para.strip()
        if not para:
            continue
        story.append(Paragraph(para, s["Body2"]))
        story.append(Spacer(1, 7))

    story.append(Spacer(1, 12))
    _hr(story)
    story.append(Paragraph(
        "<b>Disclaimer:</b> This report is produced for educational purposes only "
        "and does not constitute investment advice. Backtested results are "
        "hypothetical; they exclude taxes, borrowing costs, and real-world market "
        "frictions such as bid-ask spreads beyond the modelled slippage, and they "
        "do not guarantee future performance. Results on a single ticker over one "
        "time window have limited generalisability.",
        s["Small"]))

    doc = SimpleDocTemplate(
        str(out_path), pagesize=A4,
        leftMargin=1.8*cm, rightMargin=1.8*cm,
        topMargin=1.6*cm, bottomMargin=1.6*cm,
        title=f"Backtest Report — {ticker}",
    )
    doc.build(story)
    return out_path
