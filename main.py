#!/usr/bin/env python3
"""
🚀 MAIN TRADING SYSTEM CONTROLLER

Central command for the Swing Trading System.
Features:
- Scans NIFTY 50 + Indices
- Runs SuperTrend Pivot + BB Mean Reversion Strategies
- Generates Consolidated Telegram Report
"""

from datetime import datetime
from swing_strategies import NIFTY50
from daily_swing_scan import get_swing_signals, send_telegram_report

# Add Indices to the scan list
WATCHLIST = ["^NSEI", "^NSEBANK"] + NIFTY50

def run_daily_scan():
    """Run the daily swing trading scan."""
    print("=" * 60)
    print(f"🚀 MAIN SCANNER STARTED ({datetime.now().strftime('%Y-%m-%d %H:%M')})")
    print(f"Scanning {len(WATCHLIST)} symbols (Nifty50 + Indices)...")
    print("=" * 60)
    
    # 1. Run Swing Scan
    signals = get_swing_signals(WATCHLIST)
    
    print("\n\n✅ Scan Complete.")
    
    if signals:
        print(f"\nFound {len(signals)} signals!")
        for s in signals:
            print(f"  • {s['symbol']} ({s['strategy']}) -> {s['signal']}")
    else:
        print("\nNo signals found today.")
    
    # 2. Send Report
    send_telegram_report(signals)
    print("\n📩 Telegram report sent.")
    print("=" * 60)

if __name__ == "__main__":
    run_daily_scan()
