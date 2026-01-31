"""
Nifty 50 - 6 Month Detailed Analysis with Trade Simulation.

Scans all Nifty 50 stocks with both strategies.
Simulates trades with ₹1,00,000 starting capital.
Generates comprehensive tables and summary.
"""

from strategies.rsi_divergence import RSIDivergenceStrategy
from strategies.vwap_breakout import VWAPStrategy
import pandas as pd
import yfinance as yf
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

# Configuration
STARTING_CAPITAL = 100000  # ₹1,00,000
RISK_PER_TRADE = 0.02  # 2% risk per trade

# Nifty 50 Symbols
NIFTY_50 = [
    "RELIANCE", "TCS", "HDFCBANK", "ICICIBANK", "INFY", "HINDUNILVR", "ITC",
    "SBIN", "BHARTIARTL", "KOTAKBANK", "LT", "HCLTECH", "AXISBANK", "ASIANPAINT",
    "MARUTI", "SUNPHARMA", "TITAN", "ULTRACEMCO", "BAJFINANCE", "WIPRO",
    "NESTLEIND", "TATAMOTORS", "M&M", "NTPC", "POWERGRID", "TECHM", "TATASTEEL",
    "ADANIENT", "ADANIPORTS", "JSWSTEEL", "ONGC", "COALINDIA", "BAJAJFINSV",
    "HDFCLIFE", "DRREDDY", "DIVISLAB", "GRASIM", "CIPLA", "APOLLOHOSP",
    "BRITANNIA", "EICHERMOT", "SBILIFE", "BPCL", "TATACONSUM", "INDUSINDBK",
    "HINDALCO", "HEROMOTOCO", "UPL"
]

STRATEGIES = [
    RSIDivergenceStrategy(),
    VWAPStrategy()
]


def simulate_trades(signals, data, capital):
    """Simulate trades and calculate P&L."""
    trades = []
    current_capital = capital
    
    df = data.copy()
    df.columns = [c.lower() for c in df.columns]
    
    for sig in signals:
        entry_price = sig['price']
        sl = sig['sl']
        tp = sig['tp']
        sig_time = sig['time']
        action = sig['action']
        
        try:
            sig_idx = df.index.get_loc(sig_time)
        except:
            continue
        
        trade_result = None
        exit_price = None
        
        for i in range(sig_idx + 1, min(sig_idx + 30, len(df))):
            h = df['high'].iloc[i]
            l = df['low'].iloc[i]
            
            if action == 'BUY':
                if l <= sl:
                    trade_result = 'LOSS'
                    exit_price = sl
                    break
                elif h >= tp:
                    trade_result = 'WIN'
                    exit_price = tp
                    break
            else:
                if h >= sl:
                    trade_result = 'LOSS'
                    exit_price = sl
                    break
                elif l <= tp:
                    trade_result = 'WIN'
                    exit_price = tp
                    break
        
        if trade_result is None:
            trade_result = 'OPEN'
            exit_price = df['close'].iloc[min(sig_idx + 29, len(df) - 1)]
        
        if action == 'BUY':
            pnl_pct = ((exit_price - entry_price) / entry_price) * 100
            risk_amt = (entry_price - sl) / entry_price if entry_price > sl else 0.02
        else:
            pnl_pct = ((entry_price - exit_price) / entry_price) * 100
            risk_amt = (sl - entry_price) / entry_price if sl > entry_price else 0.02
        
        if risk_amt <= 0:
            risk_amt = 0.02
        
        position_size = min((current_capital * RISK_PER_TRADE) / risk_amt, current_capital)
        pnl_amount = position_size * (pnl_pct / 100)
        current_capital += pnl_amount
        
        trades.append({
            'time': sig_time,
            'action': action,
            'entry': entry_price,
            'sl': sl,
            'tp': tp,
            'exit': exit_price,
            'result': trade_result,
            'pnl_pct': pnl_pct,
            'pnl_amt': pnl_amount
        })
    
    return trades, current_capital


def analyze_symbol(symbol, strategies):
    """Analyze a symbol with all strategies."""
    results = []
    
    try:
        ticker = f"{symbol}.NS"
        data = yf.download(ticker, period="6mo", interval="1d", progress=False)
        
        if isinstance(data.columns, pd.MultiIndex):
            data.columns = data.columns.get_level_values(0)
        
        if data.empty or len(data) < 50:
            return results
        
        df = data.copy()
        df.columns = [c.lower() for c in df.columns]
        
        for strat in strategies:
            try:
                signals = strat.check_signals(df)
                
                if signals:
                    trades, final_cap = simulate_trades(signals, data, STARTING_CAPITAL)
                    
                    wins = len([t for t in trades if t['result'] == 'WIN'])
                    losses = len([t for t in trades if t['result'] == 'LOSS'])
                    total = len(trades)
                    win_rate = (wins / total * 100) if total > 0 else 0
                    pnl = final_cap - STARTING_CAPITAL
                    return_pct = (pnl / STARTING_CAPITAL) * 100
                    
                    results.append({
                        'symbol': symbol,
                        'strategy': strat.name(),
                        'signals': len(signals),
                        'trades': total,
                        'wins': wins,
                        'losses': losses,
                        'win_rate': win_rate,
                        'pnl': pnl,
                        'return_pct': return_pct,
                        'final_capital': final_cap,
                        'trade_details': trades
                    })
            except:
                pass
    except:
        pass
    
    return results


def main():
    print("=" * 80)
    print("  📊 NIFTY 50 - 6 MONTH DETAILED ANALYSIS")
    print("=" * 80)
    print(f"💰 Starting Capital: ₹{STARTING_CAPITAL:,}")
    print(f"⚠️  Risk per Trade: {RISK_PER_TRADE*100}%")
    print(f"📅 Period: Last 6 Months")
    print(f"📈 Symbols: {len(NIFTY_50)} Nifty 50 stocks")
    print()
    
    all_results = []
    
    for i, symbol in enumerate(NIFTY_50):
        progress = (i + 1) / len(NIFTY_50) * 100
        print(f"\r[{progress:5.1f}%] Analyzing {symbol}...", end="", flush=True)
        
        results = analyze_symbol(symbol, STRATEGIES)
        all_results.extend(results)
    
    print("\n")
    
    if not all_results:
        print("No results found!")
        return
    
    df = pd.DataFrame(all_results)
    
    # ============================================
    # TABLE 1: Results by Symbol
    # ============================================
    print("=" * 80)
    print("  📈 RESULTS BY SYMBOL (Top 15 by Return)")
    print("=" * 80)
    
    symbol_df = df.groupby('symbol').agg({
        'signals': 'sum',
        'trades': 'sum',
        'wins': 'sum',
        'losses': 'sum',
        'pnl': 'sum',
        'return_pct': 'mean'
    }).round(2)
    
    symbol_df['win_rate'] = (symbol_df['wins'] / symbol_df['trades'] * 100).round(1)
    symbol_df = symbol_df.sort_values('pnl', ascending=False)
    
    print(f"\n{'Symbol':<12} {'Signals':>8} {'Trades':>7} {'Wins':>5} {'Losses':>6} {'Win%':>6} {'P&L (₹)':>12} {'Return%':>9}")
    print("-" * 80)
    
    for symbol, row in symbol_df.head(15).iterrows():
        pnl_str = f"₹{row['pnl']:+,.0f}"
        print(f"{symbol:<12} {int(row['signals']):>8} {int(row['trades']):>7} {int(row['wins']):>5} "
              f"{int(row['losses']):>6} {row['win_rate']:>5.1f}% {pnl_str:>12} {row['return_pct']:>+8.2f}%")
    
    # ============================================
    # TABLE 2: Results by Strategy
    # ============================================
    print("\n" + "=" * 80)
    print("  📊 RESULTS BY STRATEGY")
    print("=" * 80)
    
    strat_df = df.groupby('strategy').agg({
        'signals': 'sum',
        'trades': 'sum',
        'wins': 'sum',
        'losses': 'sum',
        'pnl': 'sum',
        'return_pct': 'mean'
    }).round(2)
    
    strat_df['win_rate'] = (strat_df['wins'] / strat_df['trades'] * 100).round(1)
    
    print(f"\n{'Strategy':<20} {'Signals':>8} {'Trades':>7} {'Wins':>5} {'Losses':>6} {'Win%':>6} {'Total P&L':>14} {'Avg Return%':>12}")
    print("-" * 80)
    
    for strat, row in strat_df.iterrows():
        pnl_str = f"₹{row['pnl']:+,.0f}"
        print(f"{strat:<20} {int(row['signals']):>8} {int(row['trades']):>7} {int(row['wins']):>5} "
              f"{int(row['losses']):>6} {row['win_rate']:>5.1f}% {pnl_str:>14} {row['return_pct']:>+11.2f}%")
    
    # ============================================
    # TABLE 3: Top Profitable Trades
    # ============================================
    print("\n" + "=" * 80)
    print("  🏆 TOP 10 PROFITABLE SYMBOL-STRATEGY COMBINATIONS")
    print("=" * 80)
    
    top_df = df[df['pnl'] > 0].sort_values('pnl', ascending=False).head(10)
    
    print(f"\n{'Symbol':<12} {'Strategy':<18} {'Trades':>6} {'Wins':>5} {'Win%':>6} {'P&L (₹)':>12} {'Return%':>9}")
    print("-" * 80)
    
    for _, row in top_df.iterrows():
        pnl_str = f"₹{row['pnl']:+,.0f}"
        print(f"{row['symbol']:<12} {row['strategy']:<18} {row['trades']:>6} {row['wins']:>5} "
              f"{row['win_rate']:>5.1f}% {pnl_str:>12} {row['return_pct']:>+8.2f}%")
    
    # ============================================
    # TABLE 4: Losing Combinations (for review)
    # ============================================
    print("\n" + "=" * 80)
    print("  ⚠️  BOTTOM 10 COMBINATIONS (Review Required)")
    print("=" * 80)
    
    bottom_df = df[df['pnl'] < 0].sort_values('pnl').head(10)
    
    print(f"\n{'Symbol':<12} {'Strategy':<18} {'Trades':>6} {'Wins':>5} {'Win%':>6} {'P&L (₹)':>12} {'Return%':>9}")
    print("-" * 80)
    
    for _, row in bottom_df.iterrows():
        pnl_str = f"₹{row['pnl']:,.0f}"
        print(f"{row['symbol']:<12} {row['strategy']:<18} {row['trades']:>6} {row['wins']:>5} "
              f"{row['win_rate']:>5.1f}% {pnl_str:>12} {row['return_pct']:>+8.2f}%")
    
    # ============================================
    # GRAND SUMMARY
    # ============================================
    total_signals = df['signals'].sum()
    total_trades = df['trades'].sum()
    total_wins = df['wins'].sum()
    total_pnl = df['pnl'].sum()
    overall_win_rate = (total_wins / total_trades * 100) if total_trades > 0 else 0
    
    # Portfolio simulation (sequential trades)
    portfolio_capital = STARTING_CAPITAL
    avg_return = df['return_pct'].mean()
    
    print("\n" + "=" * 80)
    print("  💰 GRAND SUMMARY")
    print("=" * 80)
    print(f"""
    📊 Total Symbols Analyzed: {len(symbol_df)}
    📈 Total Signals Generated: {total_signals}
    🔄 Total Trades Executed: {total_trades}
    ✅ Winning Trades: {total_wins}
    ❌ Losing Trades: {total_trades - total_wins}
    📊 Overall Win Rate: {overall_win_rate:.1f}%
    
    💰 Starting Capital: ₹{STARTING_CAPITAL:,}
    📈 Sum of All P&L: ₹{total_pnl:+,.2f}
    📊 Average Return per Symbol-Strategy: {avg_return:+.2f}%
    
    🏆 Best Performer: {symbol_df.index[0]} (₹{symbol_df.iloc[0]['pnl']:+,.0f})
    ⚠️  Worst Performer: {symbol_df.index[-1]} (₹{symbol_df.iloc[-1]['pnl']:+,.0f})
    """)
    
    # Save detailed report
    report_df = df[['symbol', 'strategy', 'signals', 'trades', 'wins', 'losses', 
                    'win_rate', 'pnl', 'return_pct', 'final_capital']]
    report_df.to_csv('nifty50_6month_analysis.csv', index=False)
    
    print("=" * 80)
    print(f"📁 Detailed report saved: nifty50_6month_analysis.csv")
    print("=" * 80)


if __name__ == "__main__":
    main()
