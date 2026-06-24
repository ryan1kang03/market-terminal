# Apex Market Terminal

A real-time market data terminal built with Python and the Alpaca API.
Streams live bid/ask quotes, displays last trade prices, and visualizes
30 days of historical OHLCV data in a Bloomberg-style dark terminal UI.

---

## Features

- Live bid/ask quote polling via Alpaca Paper Trading API
- Last trade price display updated every 3 seconds
- 30-day historical OHLCV chart with open, high, low, close, and volume
- Live sparkline price chart that builds up over the session
- Session stats: high, low, tick count, average mid, latency
- Quick-select buttons for AAPL, TSLA, NVDA, SPY, MSFT
- Feed log showing every quote with timestamps

---

## Setup

**1. Clone the repo**

    git clone https://github.com/ryan1kang03/market-terminal.git
    cd market-terminal

**2. Install dependencies**

    pip install -r requirements.txt

**3. Create your .env file**

Sign up for a free paper trading account at alpaca.markets
Then create a .env file in the project root:

    APCA_API_KEY_ID=your_key_here
    APCA_API_SECRET_KEY=your_secret_here

Never commit your .env file — it is already in .gitignore

**4. Run the terminal**

    python main.py

---

## How It Works

1. On launch a 30-day OHLCV chart loads for AAPL
2. After closing the chart the live terminal UI opens
3. Type any ticker or use the quick-select buttons and click CONNECT
4. The terminal polls Alpaca every 3 seconds for bid, ask, and last trade
5. The sparkline chart builds up live with each new quote
6. All quotes are logged in the feed log with timestamps

---

## Built With

- alpaca-py — Alpaca Markets Python SDK
- Tkinter — UI framework
- Matplotlib — Historical OHLCV chart
- pandas — Data handling
- python-dotenv — Environment variables
