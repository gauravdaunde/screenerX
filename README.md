# 📈 VWAP Trading Strategy Screener

A production-ready automated trading system for Indian stocks (NSE) using VWAP breakout strategy with Dhan API integration.

## ✨ Features

| Feature | Status |
|---------|--------|
| 📊 VWAP Breakout Strategy | ✅ Optimized |
| 🔍 Nifty 50 Scanner | ✅ Ready |
| 🤖 Auto-Trading (Dhan API) | ✅ Ready |
| 📱 Telegram Alerts | ✅ Working |
| 📈 Backtesting | ✅ Available |
| 🧪 Sandbox Mode | ✅ Default |

---

## 🚀 Quick Start

### 1. Installation

```bash
# Clone and setup
cd screener
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install -r requirements.txt
```

### 2. Configuration

Create `.env` file:
```env
# Dhan API (get from api.dhan.co)
DHAN_CLIENT_ID=your_client_id
DHAN_ACCESS_TOKEN=your_access_token

# Telegram (get from @BotFather)
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id
```

### 3. Run

```bash
# Scan Nifty 50 for signals
python nifty50_scanner.py

# Auto-trade (DRY RUN by default)
python auto_trader.py

# Backtest strategy
python nifty50_analysis.py
```

---

## 📊 Strategy: VWAP Breakout

### Logic
```
BUY Signal:  Price crosses ABOVE VWAP AND Close > EMA(13)
SELL Signal: Price crosses BELOW VWAP AND Close < EMA(13)
Stop-Loss:   1.5 × ATR below/above entry
Target:      2 × Risk (1:2 R:R ratio)
```

### Optimized Parameters
| Parameter | Value | Found By |
|-----------|-------|----------|
| VWAP Period | 10 | Backtesting |
| EMA Period | 13 | Backtesting |
| R:R Ratio | 2.0 | Optimization |

### Performance (6-month backtest)
- **Win Rate:** ~50-60%
- **Best on:** RELIANCE, TCS, HDFCBANK
- **Timeframe:** Daily (1d)

---

## 🤖 Auto-Trading System

### Architecture
```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  YFinance Data  │────▶│  VWAP Scanner   │────▶│   Dhan API      │
│  (Historical)   │     │  (Signal Gen)   │     │  (Order Exec)   │
└─────────────────┘     └────────┬────────┘     └────────┬────────┘
                                 │                       │
                                 ▼                       ▼
                        ┌─────────────────┐     ┌─────────────────┐
                        │ Position Sizing │     │ Telegram Alert  │
                        │ (2% Risk Mgmt)  │     │ (Notifications) │
                        └─────────────────┘     └─────────────────┘
```

### Configuration

| Setting | Default | Description |
|---------|---------|-------------|
| `CAPITAL_PER_TRADE` | ₹1,00,000 | Full capital per trade |
| `MAX_RISK_PER_TRADE` | 2% | Maximum risk per trade |
| `MAX_ORDERS_PER_DAY` | 3 | Daily order limit |
| `DRY_RUN` | True | Paper trading mode |

### Modes

| Mode | Setting | Description |
|------|---------|-------------|
| 🧪 Sandbox | Default | Uses Dhan sandbox (fake money) |
| 📝 Dry Run | `DRY_RUN=True` | Simulates without API calls |
| 🔴 Live | `DRY_RUN=False` + Prod API | Real money trading |

---

## 📁 Project Structure

```
screener/
├── auto_trader.py        # 🤖 Main auto-trading system
├── nifty50_scanner.py    # 🔍 Nifty 50 signal scanner
├── nifty50_analysis.py   # 📊 6-month backtest analysis
├── backtest_runner.py    # 🧪 Backtesting engine
├── data_fetcher.py       # 📥 Data fetching (YFinance/Dhan)
├── config.py             # ⚙️ Configuration
├── strategies/
│   ├── base.py           # Base strategy class
│   ├── vwap_breakout.py  # 📈 VWAP strategy (primary)
│   └── rsi_divergence.py # 📉 RSI strategy (secondary)
├── .env                  # 🔑 API credentials
└── requirements.txt      # 📦 Dependencies
```

---

## 📱 Telegram Alerts

### Setup
1. Create bot via [@BotFather](https://t.me/BotFather)
2. Get your Chat ID via [@userinfobot](https://t.me/userinfobot)
3. Add to `.env`

### Alert Examples

**Signal Alert:**
```
🟢 BUY SIGNAL - RELIANCE

📊 Strategy: VWAP_V10_E13
💰 Entry: ₹1,400.00
🛑 Stop Loss: ₹1,375.00
🎯 Target: ₹1,450.00
```

**Order Alert:**
```
🟢 ORDER PLACED

📈 Symbol: RELIANCE
📦 Quantity: 71 shares
💰 Entry: ₹1,400.00
🔖 Order ID: 712601312011
```

---

## 🔧 API Reference

### Dhan API
- **Sandbox:** `https://sandbox.dhan.co/v2` (default)
- **Production:** `https://api.dhan.co/v2`
- **Docs:** [DhanHQ API](https://dhanhq.co/docs/v2/)

### Switching to Production
1. Get production token from [api.dhan.co](https://api.dhan.co)
2. Update `.env` with new `DHAN_ACCESS_TOKEN`
3. Set `DRY_RUN = False` in `auto_trader.py`

---

## 📊 Scripts Reference

| Script | Purpose | Usage |
|--------|---------|-------|
| `auto_trader.py` | Auto-trading system | `python auto_trader.py` |
| `nifty50_scanner.py` | Scan for signals | `python nifty50_scanner.py` |
| `nifty50_analysis.py` | 6-month backtest | `python nifty50_analysis.py` |
| `optimize_params.py` | Parameter optimization | `python optimize_params.py` |
| `mock_order_test.py` | Test order flow | `python mock_order_test.py` |

---

## ⚠️ Disclaimer

**This software is for educational purposes only.**

- Past performance does not guarantee future results
- Trading involves significant risk of loss
- Always paper trade before using real money
- The authors are not responsible for any financial losses

---

## 📝 License

MIT License - Use at your own risk.

---

## 🔄 Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | Feb 2026 | Initial release with VWAP strategy |
| 1.1.0 | Feb 2026 | Added Dhan API integration |
| 1.2.0 | Feb 2026 | Telegram alerts & auto-trading |
