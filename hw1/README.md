# Apex Market Terminal

A live market terminal built with Python that displays real-time stock quotes and historical charts using the Alpaca API.

## Setup

### 1. Clone the repo
```bash
git clone https://github.com/ryan1kang03/market-terminal.git
cd market-terminal
```

### 2. Install dependencies
```bash
pip install -r requirements.txt
```

### 3. Configure API keys

Create a `.env` file in the project root with your Alpaca API credentials:

Each team member needs their own free Alpaca paper trading account.
Sign up at [alpaca.markets](https://alpaca.markets), then create a
`.env` file in the project root:

```
APCA_API_KEY_ID=your_api_key_here
APCA_API_SECRET_KEY=your_api_secret_here
```

### 3. Run the terminal

```bash
python main.py
``
---

## How It Works

1. On launch a **30-day OHLCV chart** loads for AAPL using Alpaca's
   historical data API showing open, high, low, close, and volume
2. After closing the chart the **live terminal UI** opens
3. Type any ticker symbol or use the quick-select buttons and
   click **CONNECT**
4. The terminal polls Alpaca every 3 seconds for the latest
   bid price, ask price, and last trade price
5. The sparkline chart builds up live with each new quote
6. All quotes are logged in the feed log with timestamps

---

## Requirements

- Python 3.9+
- Free Alpaca paper trading account at [alpaca.markets](https://alpaca.markets)