import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.patches as mpatches
from modules.data_connector import get_historical_bars

def plot_historical_bars(symbol: str, days: int = 30):
    print(f"Loading {days} days of data for {symbol}...")
    df = get_historical_bars(symbol, days=days)
    df = df.reset_index()

    # Resample to 5-minute bars
    df = df.set_index("timestamp")
    df_5min = df.resample("5min").agg({
        "open":   "first",
        "high":   "max",
        "low":    "min",
        "close":  "last",
        "volume": "sum"
    }).dropna()
    df_5min = df_5min.reset_index()

    fig, axes = plt.subplots(2, 1, figsize=(16, 9),
                             sharex=True, facecolor="#0d1117")
    fig.suptitle(f"{symbol} — Last {days} Days (5-Min Bars)",
                 fontsize=14, color="white", y=0.98)

    ax1 = axes[0]
    ax1.set_facecolor("#0d1117")

    # Draw candlesticks
    for _, row in df_5min.iterrows():
        color = "#00ff88" if row["close"] >= row["open"] else "#ff3355"
        # Wick
        ax1.plot([row["timestamp"], row["timestamp"]],
                 [row["low"], row["high"]],
                 color=color, linewidth=0.5, alpha=0.6)
        # Body
        ax1.add_patch(mpatches.FancyBboxPatch(
            (mdates.date2num(row["timestamp"].to_pydatetime()) - 0.001,
             min(row["open"], row["close"])),
            0.002,
            abs(row["close"] - row["open"]) or 0.01,
            boxstyle="square,pad=0",
            facecolor=color, edgecolor=color, linewidth=0
        ))

    ax1.set_ylabel("Price (USD)", color="white")
    ax1.tick_params(colors="white")
    ax1.spines["bottom"].set_color("#1a2d42")
    ax1.spines["top"].set_color("#1a2d42")
    ax1.spines["left"].set_color("#1a2d42")
    ax1.spines["right"].set_color("#1a2d42")
    ax1.grid(True, alpha=0.15, color="#1a2d42")

    green_patch = mpatches.Patch(color="#00ff88", label="Bullish (Close > Open)")
    red_patch   = mpatches.Patch(color="#ff3355", label="Bearish (Close < Open)")
    ax1.legend(handles=[green_patch, red_patch], facecolor="#111c27",
               labelcolor="white", loc="upper left")

    # Volume
    ax2 = axes[1]
    ax2.set_facecolor("#0d1117")
    colors = ["#00ff88" if row["close"] >= row["open"] else "#ff3355"
              for _, row in df_5min.iterrows()]
    ax2.bar(df_5min["timestamp"], df_5min["volume"],
            color=colors, alpha=0.7, width=0.002)
    ax2.set_ylabel("Volume", color="white")
    ax2.set_xlabel("Date", color="white")
    ax2.tick_params(colors="white")
    ax2.spines["bottom"].set_color("#1a2d42")
    ax2.spines["top"].set_color("#1a2d42")
    ax2.spines["left"].set_color("#1a2d42")
    ax2.spines["right"].set_color("#1a2d42")
    ax2.grid(True, alpha=0.15, color="#1a2d42")

    ax1.xaxis.set_major_formatter(mdates.DateFormatter("%m/%d"))
    ax1.xaxis.set_major_locator(mdates.DayLocator(interval=2))
    plt.xticks(rotation=45, color="white")
    plt.tight_layout()
    plt.show()