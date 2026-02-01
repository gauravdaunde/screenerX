#!/usr/bin/env python3
"""
SuperTrend + Pivot Point Strategy Backtest

Tests the CA Rachana Ranade inspired strategy on Nifty 50 stocks.
Includes trailing stop and capital analysis.
"""

import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime
from dataclasses import dataclass
from typing import List, Dict, Tuple
import warnings
warnings.filterwarnings('ignore')

from swing_strategies.supertrend_pivot import (
    calculate_supertrend,
    calculate_pivot_points,
    calculate_atr,
    get_swing_points,
    get_volume_ratio
)


# Nifty 50 stocks
NIFTY50 = [
    "RELIANCE", "TCS", "HDFCBANK", "ICICIBANK", "INFY", "HINDUNILVR",
    "ITC", "SBIN", "BHARTIARTL", "KOTAKBANK", "LT", "HCLTECH",
    "AXISBANK", "ASIANPAINT", "MARUTI", "SUNPHARMA", "TITAN",
    "BAJFINANCE", "WIPRO", "NTPC", "POWERGRID", "TECHM",
    "TATASTEEL", "ONGC", "COALINDIA", "DRREDDY", "CIPLA",
    "BRITANNIA", "HINDALCO", "JSWSTEEL"
]


@dataclass
class Trade:
    symbol: str
    signal: str
    entry_date: datetime
    exit_date: datetime
    entry_price: float
    exit_price: float
    stop_loss: float
    target: float
    pnl: float
    pnl_pct: float
    duration: int
    result: str
    exit_reason: str
    pivot_level: str


class SuperTrendPivotBacktester:
    """Backtester for SuperTrend + Pivot strategy."""
    
    def __init__(self,
                 max_hold_days: int = 10,
                 trailing_activation: float = 0.01,
                 trailing_distance: float = 0.015):
        self.max_hold_days = max_hold_days
        self.trailing_activation = trailing_activation
        self.trailing_distance = trailing_distance
    
    def fetch_data(self, symbol: str, years: int = 2) -> pd.DataFrame:
        """Fetch historical data."""
        ticker = f"{symbol}.NS"
        
        try:
            data = yf.download(ticker, period=f"{years}y", interval="1d", progress=False)
            
            if isinstance(data.columns, pd.MultiIndex):
                data.columns = data.columns.get_level_values(0)
            
            data.columns = [c.lower() for c in data.columns]
            return data
        except:
            return pd.DataFrame()
    
    def check_signal(self, df: pd.DataFrame, idx: int) -> Tuple[str, float, float, float, str, float]:
        """
        Check for buy/sell signal at given index.
        
        Returns: (signal, stop_loss, target, confidence, pivot_level, st_value)
        """
        if idx < 50:
            return "HOLD", 0, 0, 0, "", 0
        
        window = df.iloc[:idx+1].copy()
        
        # Calculate indicators
        supertrend, direction = calculate_supertrend(window)
        pivots = calculate_pivot_points(window)
        atr = calculate_atr(window)
        swing_high, swing_low = get_swing_points(window)
        volume_ratio = get_volume_ratio(window)
        
        close = window['close'].iloc[-1]
        prev_close = window['close'].iloc[-2]
        high = window['high'].iloc[-1]
        low = window['low'].iloc[-1]
        open_price = window['open'].iloc[-1]
        st_value = supertrend.iloc[-1]
        st_direction = direction.iloc[-1]
        
        # Candle analysis
        candle_body = abs(close - open_price)
        candle_range = high - low
        body_ratio = candle_body / candle_range if candle_range > 0 else 0
        is_bullish = close > open_price
        is_bearish = close < open_price
        close_near_high = (high - close) / candle_range < 0.25 if candle_range > 0 else False
        close_near_low = (close - low) / candle_range < 0.25 if candle_range > 0 else False
        
        # Wick analysis
        upper_wick = high - max(open_price, close)
        lower_wick = min(open_price, close) - low
        wick_ratio = (upper_wick + lower_wick) / candle_range if candle_range > 0 else 0
        
        # Avoid conditions
        if volume_ratio < 0.7:
            return "HOLD", 0, 0, 0, "", 0
        
        if wick_ratio > 0.7:
            return "HOLD", 0, 0, 0, "", 0
        
        if not pivots:
            return "HOLD", 0, 0, 0, "", 0
        
        # Check for BUY signal
        if st_direction == 1:  # SuperTrend Bullish
            r1 = pivots['R1']
            r2 = pivots['R2']
            
            # Breakout above R1
            if close > r1 and prev_close <= r1:
                confidence = 0.5
                
                if is_bullish:
                    confidence += 0.1
                if close_near_high:
                    confidence += 0.1
                if volume_ratio > 1.2:
                    confidence += 0.1
                if body_ratio > 0.5:
                    confidence += 0.1
                
                if confidence >= 0.6:
                    # Stop loss
                    stop_loss = max(st_value, swing_low, close - 1.5 * atr)
                    
                    # Target
                    risk = close - stop_loss
                    target = max(r2, close + 2 * risk)
                    
                    return "BUY", stop_loss, target, confidence, "R1", st_value
        
        # Check for SELL signal
        elif st_direction == -1:  # SuperTrend Bearish
            s1 = pivots['S1']
            s2 = pivots['S2']
            
            # Breakdown below S1
            if close < s1 and prev_close >= s1:
                confidence = 0.5
                
                if is_bearish:
                    confidence += 0.1
                if close_near_low:
                    confidence += 0.1
                if volume_ratio > 1.2:
                    confidence += 0.1
                if body_ratio > 0.5:
                    confidence += 0.1
                
                if confidence >= 0.6:
                    # Stop loss
                    stop_loss = min(st_value, swing_high, close + 1.5 * atr)
                    
                    # Target
                    risk = stop_loss - close
                    target = min(s2, close - 2 * risk)
                    
                    return "SELL", stop_loss, target, confidence, "S1", st_value
        
        return "HOLD", 0, 0, 0, "", 0
    
    def simulate_trade(self, df: pd.DataFrame, entry_idx: int,
                       signal: str, entry_price: float,
                       stop_loss: float, target: float,
                       st_value: float) -> Tuple[int, float, str]:
        """
        Simulate trade with trailing stop.
        
        Returns: (exit_idx, exit_price, exit_reason)
        """
        trailing_stop = stop_loss
        best_price = entry_price
        
        for i in range(1, self.max_hold_days + 1):
            curr_idx = entry_idx + i
            if curr_idx >= len(df):
                return curr_idx - 1, df['close'].iloc[-1], "DATA_END"
            
            high = df['high'].iloc[curr_idx]
            low = df['low'].iloc[curr_idx]
            close = df['close'].iloc[curr_idx]
            
            if signal == "BUY":
                best_price = max(best_price, high)
                
                # Trailing stop activation
                profit_pct = (best_price - entry_price) / entry_price
                if profit_pct >= self.trailing_activation:
                    new_trail = best_price * (1 - self.trailing_distance)
                    trailing_stop = max(trailing_stop, new_trail)
                
                # Check stops
                if low <= trailing_stop:
                    exit_price = max(trailing_stop, low)
                    reason = "TRAILING_STOP" if trailing_stop > stop_loss else "STOP_LOSS"
                    return curr_idx, exit_price, reason
                
                # Check target
                if high >= target:
                    return curr_idx, target, "TARGET"
                    
            else:  # SELL
                best_price = min(best_price, low)
                
                profit_pct = (entry_price - best_price) / entry_price
                if profit_pct >= self.trailing_activation:
                    new_trail = best_price * (1 + self.trailing_distance)
                    trailing_stop = min(trailing_stop, new_trail)
                
                if high >= trailing_stop:
                    exit_price = min(trailing_stop, high)
                    reason = "TRAILING_STOP" if trailing_stop < stop_loss else "STOP_LOSS"
                    return curr_idx, exit_price, reason
                
                if low <= target:
                    return curr_idx, target, "TARGET"
        
        return entry_idx + self.max_hold_days, df['close'].iloc[min(entry_idx + self.max_hold_days, len(df)-1)], "MAX_HOLD"
    
    def backtest_stock(self, symbol: str) -> List[Trade]:
        """Backtest strategy on single stock."""
        df = self.fetch_data(symbol)
        
        if df.empty or len(df) < 250:
            return []
        
        trades = []
        i = 100
        
        while i < len(df) - self.max_hold_days:
            signal, stop_loss, target, confidence, pivot_level, st_value = self.check_signal(df, i)
            
            if signal != "HOLD":
                entry_date = df.index[i]
                entry_price = df['close'].iloc[i]
                
                # Simulate trade
                exit_idx, exit_price, exit_reason = self.simulate_trade(
                    df, i, signal, entry_price, stop_loss, target, st_value
                )
                
                exit_date = df.index[exit_idx]
                duration = (exit_date - entry_date).days
                
                # Calculate P&L
                if signal == "BUY":
                    pnl = exit_price - entry_price
                else:
                    pnl = entry_price - exit_price
                
                pnl_pct = (pnl / entry_price) * 100
                result = "WIN" if pnl > 0 else "LOSS"
                
                trades.append(Trade(
                    symbol=symbol,
                    signal=signal,
                    entry_date=entry_date,
                    exit_date=exit_date,
                    entry_price=entry_price,
                    exit_price=exit_price,
                    stop_loss=stop_loss,
                    target=target,
                    pnl=pnl,
                    pnl_pct=pnl_pct,
                    duration=duration,
                    result=result,
                    exit_reason=exit_reason,
                    pivot_level=pivot_level
                ))
                
                i = exit_idx + 1
            else:
                i += 1
        
        return trades
    
    def run_backtest(self) -> Tuple[List[Trade], Dict]:
        """Run full backtest on Nifty 50."""
        all_trades = []
        stock_stats = {}
        
        print(f"\n🔍 Backtesting SuperTrend + Pivot on {len(NIFTY50)} stocks...")
        print("-" * 60)
        
        for idx, symbol in enumerate(NIFTY50):
            progress = (idx + 1) / len(NIFTY50) * 100
            print(f"\r[{progress:5.1f}%] {symbol:<15}", end="", flush=True)
            
            trades = self.backtest_stock(symbol)
            
            if trades:
                all_trades.extend(trades)
                
                wins = sum(1 for t in trades if t.result == "WIN")
                total_pnl = sum(t.pnl_pct for t in trades)
                
                stock_stats[symbol] = {
                    'trades': len(trades),
                    'wins': wins,
                    'win_rate': (wins / len(trades) * 100) if trades else 0,
                    'total_pnl': total_pnl,
                    'avg_pnl': total_pnl / len(trades) if trades else 0
                }
        
        print("\n")
        return all_trades, stock_stats


def generate_report(trades: List[Trade], stock_stats: Dict, base_capital: float):
    """Generate comprehensive report."""
    
    if not trades:
        print("❌ No trades generated")
        return
    
    # Sort by date
    trades_sorted = sorted(trades, key=lambda t: t.entry_date)
    
    # Capital simulation
    capital = base_capital
    peak = base_capital
    max_drawdown = 0
    monthly_pnl = {}
    
    for trade in trades_sorted:
        scaled_pnl = capital * 0.05 * (trade.pnl_pct / 100)
        capital += scaled_pnl
        peak = max(peak, capital)
        dd = (peak - capital) / peak * 100
        max_drawdown = max(max_drawdown, dd)
        
        month_key = trade.entry_date.strftime('%Y-%m')
        if month_key not in monthly_pnl:
            monthly_pnl[month_key] = 0
        monthly_pnl[month_key] += scaled_pnl
    
    total_return = (capital - base_capital) / base_capital * 100
    
    # Statistics
    total_trades = len(trades_sorted)
    wins = sum(1 for t in trades_sorted if t.result == "WIN")
    win_rate = wins / total_trades * 100
    
    winning = [t for t in trades_sorted if t.pnl > 0]
    losing = [t for t in trades_sorted if t.pnl <= 0]
    
    avg_win = np.mean([t.pnl_pct for t in winning]) if winning else 0
    avg_loss = abs(np.mean([t.pnl_pct for t in losing])) if losing else 1
    risk_reward = avg_win / avg_loss if avg_loss > 0 else 0
    
    # By exit reason
    df = pd.DataFrame([{
        'symbol': t.symbol,
        'signal': t.signal,
        'entry_date': t.entry_date,
        'pnl_pct': t.pnl_pct,
        'result': t.result,
        'exit_reason': t.exit_reason,
        'pivot_level': t.pivot_level,
        'duration': t.duration
    } for t in trades_sorted])
    
    exit_stats = df.groupby('exit_reason').agg({
        'pnl_pct': ['count', 'mean'],
        'result': lambda x: (x == 'WIN').sum() / len(x) * 100
    }).round(2)
    exit_stats.columns = ['Count', 'Avg P&L %', 'Win Rate']
    
    # By signal type
    signal_stats = df.groupby('signal').agg({
        'pnl_pct': ['count', 'mean'],
        'result': lambda x: (x == 'WIN').sum() / len(x) * 100
    }).round(2)
    signal_stats.columns = ['Count', 'Avg P&L %', 'Win Rate']
    
    # Print Report
    print("\n" + "=" * 80)
    print("  📈 SUPERTREND + PIVOT POINT STRATEGY - BACKTEST RESULTS")
    print("=" * 80)
    
    print(f"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                            EXECUTIVE SUMMARY                                  ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  Base Capital:         ₹{base_capital:>12,.0f}                                       ║
║  Final Capital:        ₹{capital:>12,.0f}                                       ║
║  Total Return:         {total_return:>+12.1f}%                                        ║
║  Max Drawdown:         {max_drawdown:>12.1f}%                                        ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  Total Trades:         {total_trades:>12}                                        ║
║  Win Rate:             {win_rate:>12.1f}%                                       ║
║  Avg Win:              {avg_win:>+12.2f}%                                        ║
║  Avg Loss:             {avg_loss:>12.2f}%                                        ║
║  Risk:Reward:          {risk_reward:>12.2f}:1                                     ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  Avg Duration:         {df['duration'].mean():>12.1f} days                                  ║
╚══════════════════════════════════════════════════════════════════════════════╝
    """)
    
    print("\n📊 BY EXIT REASON:")
    print("-" * 50)
    print(exit_stats.to_string())
    
    print("\n📊 BY SIGNAL TYPE:")
    print("-" * 50)
    print(signal_stats.to_string())
    
    # Top stocks
    print("\n🏆 TOP 10 STOCKS:")
    print("-" * 60)
    sorted_stocks = sorted(stock_stats.items(), key=lambda x: x[1]['avg_pnl'], reverse=True)[:10]
    for sym, stats in sorted_stocks:
        emoji = "🟢" if stats['avg_pnl'] > 0 else "🔴"
        print(f"  {emoji} {sym:<12} | {stats['trades']:>3} trades | {stats['win_rate']:.1f}% WR | {stats['avg_pnl']:+.2f}% avg")
    
    # Monthly returns
    print("\n📅 MONTHLY RETURNS:")
    print("-" * 60)
    for month, pnl in list(monthly_pnl.items())[-12:]:
        bar_len = int(abs(pnl) / 200)
        bar = "█" * min(bar_len, 25)
        emoji = "🟢" if pnl > 0 else "🔴"
        print(f"  {month} │ {emoji} ₹{pnl:>+8,.0f} │ {bar}")
    
    # Capital comparison
    final_50k = 50000 * (1 + total_return / 100)
    final_100k = 100000 * (1 + total_return / 100)
    
    print(f"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                          CAPITAL COMPARISON                                   ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                              │    ₹50,000     │    ₹100,000    │              ║
╠══════════════════════════════╪════════════════╪════════════════╣══════════════╣
║  Final Capital               │  ₹{final_50k:>8,.0f}     │  ₹{final_100k:>9,.0f}    │              ║
║  Absolute Gain               │  ₹{final_50k-50000:>+8,.0f}     │  ₹{final_100k-100000:>+9,.0f}    │              ║
║  Monthly Average             │  ₹{(final_50k-50000)/12:>+8,.0f}     │  ₹{(final_100k-100000)/12:>+9,.0f}    │              ║
╚══════════════════════════════════════════════════════════════════════════════╝
    """)
    
    # Save
    df.to_csv('supertrend_pivot_backtest.csv', index=False)
    print(f"\n📁 Results saved: supertrend_pivot_backtest.csv")
    
    print("\n" + "=" * 80)
    print("  ✅ BACKTEST COMPLETE")
    print("=" * 80)
    
    return df


def main():
    print("=" * 80)
    print("  📈 SUPERTREND + PIVOT POINT STRATEGY BACKTEST")
    print("  Inspired by CA Rachana Ranade")
    print("=" * 80)
    
    backtester = SuperTrendPivotBacktester(
        max_hold_days=10,
        trailing_activation=0.008,   # Activate at 0.8% profit (let it run a bit)
        trailing_distance=0.008      # Tight 0.8% trail to lock profits
    )
    
    trades, stock_stats = backtester.run_backtest()
    
    print(f"✅ Generated {len(trades)} trades")
    
    generate_report(trades, stock_stats, base_capital=100000)


if __name__ == "__main__":
    main()
