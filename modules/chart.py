import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from modules.data_connector import get_historical_bars

def plot_historical_bars(symbol: str, days: int = 30):
    print(f"Loading {days} days of data for {symbol}...")
    df = get_historical_bars(symbol, days=days)

    # Reset index so we can access timestamp easily
    df = df.reset_index()

    fig, axes = plt.subplots(2, 1, figsize=(14, 8), sharex=True)
    fig.suptitle(f"{symbol} — Last {days} Days (1-Min Bars)", fontsize=14)

    # --- Price chart (OHLC using close line + high/low fill) ---
    ax1 = axes[0]
    ax1.plot(df["timestamp"], df["close"], label="Close", color="cyan", linewidth=0.8)
    ax1.fill_between(df["timestamp"], df["low"], df["high"], alpha=0.2, color="cyan", label="High/Low Range")
    ax1.set_ylabel("Price (USD)")
    ax1.legend(loc="upper left")
    ax1.grid(True, alpha=0.3)

    # --- Volume chart ---
    ax2 = axes[1]
    ax2.bar(df["timestamp"], df["volume"], color="steelblue", alpha=0.7, width=0.0005)
    ax2.set_ylabel("Volume")
    ax2.set_xlabel("Time")
    ax2.grid(True, alpha=0.3)

    # Format x-axis dates
    ax1.xaxis.set_major_formatter(mdates.DateFormatter("%m/%d"))
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.show()