# Technical Indicators & Strategy Backtesting with Alpaca

This project is a Python-based backtesting platform that downloads historical stock market data from the Alpaca Historical Market Data API and evaluates multiple algorithmic trading strategies using technical indicators.

The platform allows users to choose any stock ticker, backtest three different trading strategies, compare them against a Buy & Hold benchmark, and generate charts and a final performance report.

---

## Features

* Download 5+ years of daily OHLCV data from Alpaca
* User-selected stock ticker (AAPL, MSFT, SPY, QQQ, NVDA, etc.)
* 11 technical indicators implemented from scratch
* Three algorithmic trading strategies
* Buy & Hold benchmark comparison
* Long-only backtesting engine
* Performance metrics
* Automatically generated charts
* Automatically generated PDF report

---

## Installation

Clone the repository and install the required packages.

```bash
git clone <repository-url>
cd hw2
pip install -r requirements.txt
```

---

## Alpaca API Setup

Create a free Alpaca account and generate Paper Trading API keys.

Create a `.env` file (or use example provided) in the project root containing:

```env
APCA_API_KEY_ID=YOUR_API_KEY
APCA_API_SECRET_KEY=YOUR_SECRET_KEY
```

The project uses the free IEX market data feed.

---

## Running the Project

Run the program with any stock ticker:

```bash
python main.py --ticker AAPL --years 5
```

Examples:

```bash
python main.py --ticker MSFT --years 5
python main.py --ticker SPY --years 5
python main.py --ticker NVDA --years 5
python main.py --ticker QQQ --years 5
```

Optional parameters:

```bash
python main.py --ticker AAPL --years 5 --risk-free 0.04
```

---

## Output

Running the program automatically generates:

```
charts/
    equity_curve.png
    drawdowns.png
    price_trend_following.png
    price_mean_reversion.png
    price_custom_triple_confirmation.png

report/
    final_report.pdf
    performance_<ticker>.csv
```

---

## Trading Strategies

### Strategy 1 — Trend Following

Indicators:

* SMA
* MACD
* ADX

Entry:

* MACD > Signal
* ADX > 25
* Price > SMA-50

Exit:

* MACD < Signal

---

### Strategy 2 — Mean Reversion

Indicators:

* RSI
* Bollinger Bands

Entry:

* RSI < 30
* Price below lower Bollinger Band

Exit:

* RSI > 70
* Price above upper Bollinger Band

---

### Strategy 3 — Custom Triple Confirmation

Indicators:

* EMA
* RSI
* Chaikin Money Flow (CMF)

Entry:

* EMA-50 > EMA-200
* RSI crosses above 50
* CMF > 0

Exit:

* Price below EMA-50
* RSI > 75
* CMF < -0.05

---

## Technical Indicators

* SMA
* EMA
* MACD
* ADX
* RSI
* Stochastic Oscillator
* Williams %R
* Bollinger Bands
* ATR
* OBV
* Chaikin Money Flow (CMF)

---

## Backtesting Assumptions

* Initial Capital: $100,000
* Long-only
* No leverage
* No short selling
* Next-day open execution
* Configurable transaction cost

---

## Performance Metrics

The platform reports:

* Total Return
* CAGR
* Annualized Volatility
* Sharpe Ratio
* Sortino Ratio
* Maximum Drawdown
* Win Rate

---

## Project Structure

```
hw2/
│── main.py
│── requirements.txt
│── README.md
│── src/
│── charts/
│── report/
│── tests/
```

---

## Notes

Running it will create a report with the data visualized within the 'report' folder.

