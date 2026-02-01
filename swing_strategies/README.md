# Swing Trading Strategies

Rule-based swing trading system for Indian stocks.
**Holding Period: 2-10 days**

## 🚀 Quick Start

```python
from swing_strategies import scan_stock, scan_stocks

# Scan single stock
signal = scan_stock("RELIANCE")
print(signal)

# Scan multiple stocks
signals = scan_stocks(["RELIANCE", "TCS", "INFY", "SBIN"])
for s in signals:
    print(f"{s['symbol']}: {s['signal']} ({s['confidence']*100:.0f}%)")
```

## 📈 Strategies Included

| # | Strategy | Signal Type | Best For |
|---|----------|-------------|----------|
| 1 | EMA Crossover | Trend Shift | Trend reversals |
| 2 | RSI Reversal | Mean Reversion | Oversold/overbought |
| 3 | Trend Pullback | Trend Continuation | Strong trends |
| 4 | Swing Breakout | Breakout | Range breakouts |
| 5 | BB Mean Reversion | Mean Reversion | Sideways markets |
| 6 | MACD Momentum | Momentum | Fresh trends |
| 7 | Volatility Breakout | Breakout | Squeeze plays |

## 🎯 Signal Format

```python
{
    "symbol": "RELIANCE",
    "strategy_name": "Trend Pullback",
    "signal": "BUY",
    "confidence": 0.85,
    "stop_loss_type": "ATR",
    "target_type": "RR",
    "entry_price": 2450.50,
    "stop_loss": 2400.00,
    "target": 2550.00,
    "risk_reward": 2.0,
    "reason": "Pullback to EMA20 in uptrend; Bullish candle confirmation"
}
```

## ⚙️ Risk Management

| Parameter | Value |
|-----------|-------|
| Stop Loss | 1.5 × ATR or Swing Low |
| Target | 2:1 Risk-Reward minimum |
| Position Size | 2% risk per trade |
| Max Holding | 10 days |

## 🚫 Avoid Conditions

Signals are filtered out when:
- Volume < 60% of average
- RSI in neutral zone (45-55) for reversals
- No clear trend for trend strategies
- Weak breakout candles

## 📊 Full Analysis

```python
from swing_strategies import analyze_stock

analysis = analyze_stock("RELIANCE")
print(f"Trend: {analysis['market_state']['trend']}")
print(f"RSI: {analysis['market_state']['rsi']}")
print(f"Signals: {len(analysis['signals'])}")
```
