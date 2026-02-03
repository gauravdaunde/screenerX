# 📈 AlgoSwing: Automated Swing Trading System

A robust, production-ready swing trading system for **Nifty 50** stocks. It utilizes multiple strategies to identify high-probability setups and sends actionable alerts via Telegram or executes trades via the Dhan API.

## ✨ Key Features

| Component | Description | Status |
|-----------|-------------|--------|
| **Scanner** | Scans Nifty 50 + Indices daily | ✅ Active |
| **Strategy 1** | **SuperTrend + Pivot Breakout** (Trend Following) | ✅ Active |
| **Strategy 2** | **Bollinger Band Mean Reversion** (Dip Buying) | ✅ Active |
| **Alerts** | Consolidated Telegram Reports | ✅ Active |
| **Execution** | Automated Order Placement (Dhan API) | 🚧 Beta |
| **Backtesting**| 2-Year Historical Validation | ✅ Verified |

---

## 🚀 Quick Start

### 1. Installation
```bash
# Clone the repository
git clone <repo-url>
cd screener

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configuration (`.env`)
Create a `.env` file in the root directory:
```env
# Dhan API (for live trading)
DHAN_CLIENT_ID=your_id
DHAN_ACCESS_TOKEN=your_token

# Telegram Alerts (Required)
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id
```

### 3. Usage

#### ▶️ Run Daily Scan (Manual)
Run the central scanner to check all Nifty 50 stocks for potential setups:
```bash
python -m app.cron.scan
```
*This will fetch the latest data, run both strategies, and send a consolidated report to your Telegram.*

#### 🌐 Run API Server
Start the dashboard and API:
```bash
uvicorn app.main:app --reload
```
Visit http://localhost:8000/portfolio to see the dashboard.

#### ⏰ Automate Daily Scans
To run this automatically every day at market close:
👉 [See AUTOMATION.md](./AUTOMATION.md)

---

## 📊 Strategies Explained

### 1. SuperTrend + Pivot Breakout
*   **Type:** Trend Following (Momentum)
*   **Goal:** Catch big moves when a trend is establishing.
*   **Buy Logic:**
    *   Price > SuperTrend (Trend is UP)
    *   Price breaks ABOVE Pivot R1 Level
    *   Volume > Average Volume
*   **Exit:** Trailing Stop Loss (SuperTrend) or Target (3R).

### 2. Bollinger Band Mean Reversion
*   **Type:** Contrarian (Dip Buying)
*   **Goal:** Buy high-quality stocks at a discount during corrections.
*   **Buy Logic:**
    *   Price touches **Lower Bollinger Band** (Oversold)
    *   **Confirmation:** Stock is in a long-term Uptrend (Price > 200 SMA)
    *   RSI is not in extreme panic (<20).
*   **Target:** Return to Mean (20 SMA).

---

## 📁 System Architecture

```
screener/
├── app/                        # 📦 Application Core
│   ├── main.py                 #    - API Entry Point
│   ├── cron/                   #    - Scheduled Tasks (Scan)
│   ├── api/                    #    - API Routers
│   ├── services/               #    - Business Logic
│   ├── db/                     #    - Database Logic
│   └── core/                   #    - Configuration
├── auto_trader.py              # 🤖 Order Execution (Dhan API)
├── swing_strategies/           # 📚 Strategy Library
│   ├── supertrend_pivot.py     #    - SuperTrend Logic
│   └── ...
├── legacy/                     # 🏚️ Old Monolithic Files
└── AUTOMATION.md               # ⚙️ Cron Job Guide
```

---

## ⚠️ Risk Disclaimer
This software is for educational purposes only. Algo-trading involves significant financial risk.
*   **Do not** enable live trading without thorough paper trading first.
*   The authors are not responsible for any financial losses.

## 📝 License
MIT License.
