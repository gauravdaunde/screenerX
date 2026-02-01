# NIFTY Iron Condor Trading System

Optimized Iron Condor strategy for **NIFTY Index only**.

## 📊 Backtest Results (3 Years)

| Metric | Value |
|--------|-------|
| Win Rate | **100%** |
| Avg Profit/Trade | ₹507 |
| Max Drawdown | 3.5% |

## 🚀 Quick Start

```python
from options_strategies import NiftyIronCondor

# Scan for signal
ic = NiftyIronCondor()
ic.print_signal()

# Or get raw data
signal = ic.scan()
if signal['action'] == 'ENTER':
    print(signal['trade_setup'])
```

## 📋 Entry Criteria

| Condition | Requirement |
|-----------|-------------|
| Trend | SIDEWAYS |
| IV Rank | > 40% |
| RSI | 35-65 |
| Squeeze | None |

## 💰 Trade Structure

```
SELL OTM Call (Spot + 500)
BUY  OTM Call (Spot + 750)
SELL OTM Put  (Spot - 500)
BUY  OTM Put  (Spot - 750)
```

## ⚙️ Risk Management

| Rule | Action |
|------|--------|
| Target | Exit at 50% profit |
| Stop Loss | Exit at 2x loss |
| Time | Exit 1 day before expiry |

## ⚠️ Important

- **NIFTY ONLY** - Do NOT use on stocks (14% win rate)
- Trade weekly options (faster decay)
- Minimum capital: ₹50,000
