from modules.data_connector import get_historical_bars, get_latest_quote
from modules.chart import plot_historical_bars
from modules.ui import launch_ui

# Show chart first
plot_historical_bars("AAPL", days=30)

# Then launch the live UI
from modules.ui import launch_ui
launch_ui()