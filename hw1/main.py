from modules.chart import plot_historical_bars
from modules.ui import launch_ui

symbol = input("Enter symbol for historical chart (default: AAPL): ").upper().strip()
if not symbol:
    symbol = "AAPL"

plot_historical_bars(symbol, days=30)
launch_ui()