import os
from dotenv import load_dotenv
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest, StockLatestQuoteRequest
from alpaca.data.timeframe import TimeFrame
from datetime import datetime, timedelta

load_dotenv()

API_KEY = os.getenv("APCA_API_KEY_ID")
API_SECRET = os.getenv("APCA_API_SECRET_KEY")

# Client for market data (no base URL needed for data API)
client = StockHistoricalDataClient(API_KEY, API_SECRET)

def get_historical_bars(symbol: str, days: int = 30):
    """Download historical 5-minute OHLCV bars for a symbol."""
    request = StockBarsRequest(
        symbol_or_symbols=symbol,
        timeframe=TimeFrame.Minute,
        start=datetime.now() - timedelta(days=days),
        end=datetime.now(),
        limit=10000
    )
    bars = client.get_stock_bars(request)
    df = bars.df
    return df

def get_latest_quote(symbol: str):
    """Get the latest bid/ask quote for a symbol."""
    request = StockLatestQuoteRequest(symbol_or_symbols=symbol)
    quote = client.get_stock_latest_quote(request)
    return quote[symbol]