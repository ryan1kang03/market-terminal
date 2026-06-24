import os
from dotenv import load_dotenv
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest, StockLatestQuoteRequest, StockLatestTradeRequest
from alpaca.data.timeframe import TimeFrame
from datetime import datetime, timedelta

load_dotenv()

API_KEY = os.getenv("APCA_API_KEY_ID")
API_SECRET = os.getenv("APCA_API_SECRET_KEY")

client = StockHistoricalDataClient(API_KEY, API_SECRET)

def get_historical_bars(symbol: str, days: int = 30):
    """Download historical 1-minute OHLCV bars for a symbol."""
    request = StockBarsRequest(
        symbol_or_symbols=symbol,
        timeframe=TimeFrame.Minute,
        start=datetime.now() - timedelta(days=days),
        end=datetime.now(),
        limit=10000
    )
    bars = client.get_stock_bars(request)
    return bars.df

def get_latest_quote(symbol: str):
    """Get the latest bid/ask quote for a symbol."""
    request = StockLatestQuoteRequest(symbol_or_symbols=symbol)
    quote = client.get_stock_latest_quote(request)
    return quote[symbol]

def get_latest_trade(symbol: str):
    """Get the latest trade price for a symbol."""
    request = StockLatestTradeRequest(symbol_or_symbols=symbol)
    trade = client.get_stock_latest_trade(request)
    return trade[symbol]