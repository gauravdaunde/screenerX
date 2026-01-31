"""
Streamlined Backtest Runner.

Supports: RSI Divergence, VWAP Breakout strategies.
"""

from backtesting import Backtest, Strategy
from strategies.rsi_divergence import RSIDivergenceStrategy
from strategies.vwap_breakout import VWAPStrategy
import pandas as pd
import yfinance as yf
import os

def run_backtest(symbol, strategy_cls, output_dir="reports"):
    """
    Run backtest for a symbol using the specified strategy.
    """
    os.makedirs(output_dir, exist_ok=True)

    # Fetch Data
    ticker = symbol if symbol.startswith("^") else f"{symbol}.NS"
    
    try:
        data = yf.download(ticker, period="1y", interval="1d", progress=False)
    except Exception as e:
        print(f"Failed to download data for {symbol}: {e}")
        return None

    if data.empty:
        print(f"No data for {symbol}")
        return None
    
    # Flatten MultiIndex columns
    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.get_level_values(0)
    
    # Prepare data for strategy
    df = data.copy()
    df.columns = [c.lower() for c in df.columns]
    
    # Run strategy
    try:
        strat = strategy_cls()
        signals = strat.check_signals(df)
    except Exception as e:
        print(f"Error running strategy on {symbol}: {e}")
        return None
    
    if not signals:
        print(f"No signals for {symbol} - {strat.name()}")
        return None

    # Map signals for backtester
    signal_map = {pd.Timestamp(s['time']): s for s in signals}
    
    class BTStrategy(Strategy):
        def init(self): pass
        def next(self):
            t = self.data.index[-1]
            sig = signal_map.get(t)
            if sig:
                price = self.data.Close[-1]
                sl = sig.get('sl', price * 0.98)
                tp = sig.get('tp', price * 1.03)
                if sig['action'] == 'BUY' and sl < price < tp:
                    self.buy(sl=sl, tp=tp)
                elif sig['action'] == 'SELL' and tp < price < sl:
                    self.sell(sl=sl, tp=tp)

    # Prepare data for Backtesting.py
    data_bt = data.rename(columns={
        'open': 'Open', 'high': 'High', 'low': 'Low',
        'close': 'Close', 'volume': 'Volume'
    })

    # Run backtest
    bt = Backtest(data_bt, BTStrategy, cash=100000, commission=0.002)
    stats = bt.run()
    
    # Save report
    filename = f"{output_dir}/{symbol}_{strat.name()}"
    with open(f"{filename}_stats.txt", "w") as f:
        f.write(str(stats))
    
    trades = stats['_trades']
    if not trades.empty:
        trades.to_csv(f"{filename}_trades.csv")
    
    win_rate = stats['Win Rate [%]'] if pd.notna(stats['Win Rate [%]']) else 0
    ret = stats['Return [%]']
    print(f"{symbol} | {strat.name()} -> Trades: {stats['# Trades']}, Win: {win_rate:.1f}%, Return: {ret:.2f}%")
    
    return stats


if __name__ == "__main__":
    # Quick test
    print("Testing RSI Divergence on NIFTY...")
    run_backtest("^NSEI", RSIDivergenceStrategy)
    
    print("\nTesting VWAP Breakout on NIFTY...")
    run_backtest("^NSEI", VWAPStrategy)
