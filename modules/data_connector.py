import os
from dotenv import load_dotenv
from alpaca.data.historical import StockHistoricalDataClient
<<<<<<< HEAD
from alpaca.data.requests import StockBarsRequest, StockLatestQuoteRequest, StockLatestTradeRequest
=======
from alpaca.data.live import StockDataStream
from alpaca.data.requests import StockBarsRequest
>>>>>>> 53219dd8acafb4d1e5baa447af55900ced70f932
from alpaca.data.timeframe import TimeFrame
from datetime import datetime, timedelta

load_dotenv()

API_KEY = os.getenv("APCA_API_KEY_ID")
API_SECRET = os.getenv("APCA_API_SECRET_KEY")

client = StockHistoricalDataClient(API_KEY, API_SECRET)

def get_historical_bars(symbol: str, days: int = 30):
<<<<<<< HEAD
    """Download historical 1-minute OHLCV bars for a symbol."""
=======
>>>>>>> 53219dd8acafb4d1e5baa447af55900ced70f932
    request = StockBarsRequest(
        symbol_or_symbols=symbol,
        timeframe=TimeFrame.Minute,
        start=datetime.now() - timedelta(days=days),
        end=datetime.now(),
        limit=10000
    )
    bars = client.get_stock_bars(request)
    return bars.df

<<<<<<< HEAD
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
=======
def start_quote_stream(symbol: str, on_quote, on_error=None):
    """
    Open a WebSocket quote stream for symbol.
    on_quote(bid, ask) is called for every incoming quote.
    Returns the StockDataStream client — caller must call client.run() in a thread
    and client.stop() to shut down.
    """
    stream = StockDataStream(API_KEY, API_SECRET)

    async def handler(data):
        try:
            bid = float(data.bid_price)
            ask = float(data.ask_price)
            on_quote(bid, ask)
        except Exception as e:
            if on_error:
                on_error(e)

    stream.subscribe_quotes(handler, symbol)
    return stream
>>>>>>> 53219dd8acafb4d1e5baa447af55900ced70f932
