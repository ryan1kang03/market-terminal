"""
report.py
=========
Assemble the final PDF report with reportlab: strategy descriptions, entry/exit
rules, a performance comparison table, embedded charts, and a discussion.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    Image,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from .strategies import STRATEGY_DESCRIPTIONS


def _styles():
    s = getSampleStyleSheet()
    s.add(ParagraphStyle("Body2", parent=s["BodyText"], fontSize=9.5, leading=13.5))
    s.add(ParagraphStyle("Small", parent=s["BodyText"], fontSize=8, leading=11,
                         textColor=colors.HexColor("#555555")))
    s.add(ParagraphStyle("H2b", parent=s["Heading2"], spaceBefore=10, spaceAfter=4))
    s.add(ParagraphStyle("Caption", parent=s["BodyText"], fontSize=8,
                         alignment=1, textColor=colors.HexColor("#666666")))
    return s


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
) -> Path:
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    s = _styles()
    story = []

    # ---- Title block -----------------------------------------------------
    story.append(Paragraph("Technical Indicators & Strategy Backtesting", s["Title"]))
    story.append(Paragraph(
        f"Risk-adjusted comparison of algorithmic trading strategies on "
        f"<b>{ticker}</b>", s["Heading3"]))
    meta = (
        f"Universe: {ticker} &nbsp;|&nbsp; Lookback: {years} years daily OHLCV "
        f"&nbsp;|&nbsp; Data source: {data_source} &nbsp;|&nbsp; "
        f"Generated: {datetime.utcnow():%Y-%m-%d}"
    )
    story.append(Paragraph(meta, s["Small"]))
    story.append(Spacer(1, 8))
    story.append(Paragraph(
        "Initial capital $100,000. Long-only, no leverage, no short selling. "
        "Signals computed on the daily close and executed at the next open; a "
        "1 bp cost models slippage (Alpaca equity commissions are $0).",
        s["Small"]))
    story.append(Spacer(1, 12))

    # ---- Strategy descriptions ------------------------------------------
    story.append(Paragraph("1. Strategy descriptions & rules", s["H2b"]))
    for name, d in STRATEGY_DESCRIPTIONS.items():
        story.append(Paragraph(f"<b>{name}</b> &nbsp;<font size=8 color='#777'>"
                               f"[{d['category']}]</font>", s["Body2"]))
        story.append(Paragraph(f"<b>Entry:</b> {d['entry']}", s["Body2"]))
        story.append(Paragraph(f"<b>Exit:</b> {d['exit']}", s["Body2"]))
        story.append(Spacer(1, 6))
    story.append(Paragraph(
        "<b>Buy &amp; Hold</b> (benchmark): buy at the first open and hold to "
        "the end of the window.", s["Body2"]))
    story.append(Spacer(1, 10))

    # ---- Performance table ----------------------------------------------
    story.append(Paragraph("2. Performance comparison", s["H2b"]))
    header = ["Strategy"] + list(fmt_table.columns)
    data = [header]
    for idx, row in fmt_table.iterrows():
        data.append([idx] + [str(v) for v in row.tolist()])

    tbl = Table(data, repeatRows=1, hAlign="LEFT")
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f2937")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("ALIGN", (1, 0), (-1, -1), "CENTER"),
        ("ALIGN", (0, 0), (0, -1), "LEFT"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1),
         [colors.white, colors.HexColor("#f3f4f6")]),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#d1d5db")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(tbl)
    story.append(Spacer(1, 6))

    # Highlight best Sharpe
    best = raw_table["sharpe"].idxmax()
    story.append(Paragraph(
        f"Highest Sharpe ratio: <b>{best}</b> "
        f"({raw_table.loc[best, 'sharpe']:.2f}).", s["Small"]))
    story.append(Spacer(1, 10))

    # ---- Equity curve ----------------------------------------------------
    story.append(Paragraph("3. Equity curves", s["H2b"]))
    story.append(_img(chart_paths["equity"], width=17))
    story.append(Paragraph("Figure 1. Portfolio value over time vs Buy &amp; Hold.",
                           s["Caption"]))
    story.append(Spacer(1, 8))

    # ---- Drawdown --------------------------------------------------------
    story.append(Paragraph("4. Drawdowns", s["H2b"]))
    story.append(_img(chart_paths["drawdown"], width=17))
    story.append(Paragraph("Figure 2. Underwater plot — depth and duration of "
                           "losses from prior peaks.", s["Caption"]))
    story.append(PageBreak())

    # ---- Price charts per strategy --------------------------------------
    story.append(Paragraph("5. Price charts with signals", s["H2b"]))
    fig_n = 3
    for label, p in chart_paths.get("price", {}).items():
        story.append(_img(p, width=17))
        story.append(Paragraph(f"Figure {fig_n}. {label}: price, SMA-50/200, "
                               f"Bollinger Bands and trade markers (RSI below).",
                               s["Caption"]))
        story.append(Spacer(1, 8))
        fig_n += 1

    story.append(PageBreak())

    # ---- Discussion ------------------------------------------------------
    story.append(Paragraph("6. Discussion of results", s["H2b"]))
    for para in discussion.strip().split("\n\n"):
        story.append(Paragraph(para.strip(), s["Body2"]))
        story.append(Spacer(1, 6))

    story.append(Spacer(1, 10))
    story.append(Paragraph(
        "Disclaimer: This is an educational backtesting exercise, not "
        "investment advice. Backtested results are hypothetical, ignore taxes "
        "and some market frictions, and do not guarantee future performance.",
        s["Small"]))

    doc = SimpleDocTemplate(
        str(out_path), pagesize=A4,
        leftMargin=1.8 * cm, rightMargin=1.8 * cm,
        topMargin=1.6 * cm, bottomMargin=1.6 * cm,
        title=f"Backtest Report — {ticker}",
    )
    doc.build(story)
    return out_path


def _img(path, width=17):
    """Embed an image scaled to a target width in cm, preserving aspect."""
    from PIL import Image as PILImage

    with PILImage.open(path) as im:
        w, h = im.size
    target_w = width * cm
    target_h = target_w * h / w
    return Image(str(path), width=target_w, height=target_h)
