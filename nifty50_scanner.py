"""
Nifty 50 Background Scanner with Telegram Alerts.

Scans all Nifty 50 stocks for RSI Divergence and VWAP signals.
Sends alerts via Telegram for any new signals detected.
"""

import os
import sys
import json
import requests
from datetime import datetime
import pandas as pd
import yfinance as yf
from strategies.rsi_divergence import RSIDivergenceStrategy
from strategies.vwap_breakout import VWAPStrategy

# Telegram Config
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

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

def send_telegram_alert(message):
    """Send alert via Telegram."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print(f"[ALERT - No Telegram]: {message}")
        return False
    
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML"
    }
    
    try:
        response = requests.post(url, json=payload, timeout=10)
        return response.status_code == 200
    except Exception as e:
        print(f"Telegram error: {e}")
        return False


def format_signal_alert(symbol, signal, strategy_name):
    """Format signal as Telegram message."""
    action = signal['action']
    emoji = "🟢" if action == "BUY" else "🔴"
    
    message = f"""
{emoji} <b>{action} SIGNAL - {symbol}</b>

📊 Strategy: {strategy_name}
💰 Entry: ₹{signal['price']:.2f}
🛑 Stop Loss: ₹{signal['sl']:.2f}
🎯 Target: ₹{signal['tp']:.2f}
📝 Reason: {signal.get('reason', 'N/A')}
⏰ Time: {datetime.now().strftime('%Y-%m-%d %H:%M')}

Risk:Reward = 1:{((signal['tp'] - signal['price']) / (signal['price'] - signal['sl'])):.1f}
"""
    return message.strip()


def scan_symbol(symbol, strategies):
    """Scan a single symbol with all strategies."""
    signals_found = []
    
    try:
        ticker = f"{symbol}.NS"
        data = yf.download(ticker, period="6mo", interval="1d", progress=False)
        
        if isinstance(data.columns, pd.MultiIndex):
            data.columns = data.columns.get_level_values(0)
        
        if data.empty or len(data) < 50:
            return signals_found
        
        df = data.copy()
        df.columns = [c.lower() for c in df.columns]
        
        for strat in strategies:
            try:
                signals = strat.check_signals(df)
                
                # Only get signals from last 3 days (recent)
                for sig in signals:
                    sig_date = pd.Timestamp(sig['time']).date()
                    today = datetime.now().date()
                    days_ago = (today - sig_date).days
                    
                    if days_ago <= 3:  # Within last 3 days
                        signals_found.append({
                            'symbol': symbol,
                            'strategy': strat.name(),
                            'signal': sig,
                            'days_ago': days_ago
                        })
            except Exception as e:
                pass
    
    except Exception as e:
        pass
    
    return signals_found


def main():
    print("=" * 60)
    print("  🔍 NIFTY 50 BACKGROUND SCANNER")
    print("=" * 60)
    print(f"⏰ Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"📊 Scanning {len(NIFTY_50)} symbols with {len(STRATEGIES)} strategies")
    print()
    
    all_signals = []
    report_data = []
    
    for i, symbol in enumerate(NIFTY_50):
        progress = (i + 1) / len(NIFTY_50) * 100
        print(f"\r[{progress:5.1f}%] Scanning {symbol}...", end="", flush=True)
        
        signals = scan_symbol(symbol, STRATEGIES)
        
        if signals:
            all_signals.extend(signals)
            for s in signals:
                report_data.append({
                    'symbol': s['symbol'],
                    'strategy': s['strategy'],
                    'action': s['signal']['action'],
                    'price': s['signal']['price'],
                    'sl': s['signal']['sl'],
                    'tp': s['signal']['tp'],
                    'reason': s['signal'].get('reason', ''),
                    'date': str(s['signal']['time'])[:10],
                    'days_ago': s['days_ago']
                })
    
    print("\n")
    
    # Generate Report
    print("=" * 60)
    print("  📋 SCAN REPORT")
    print("=" * 60)
    
    if all_signals:
        print(f"\n✅ Found {len(all_signals)} recent signals:\n")
        
        # Sort by days_ago (most recent first)
        all_signals.sort(key=lambda x: x['days_ago'])
        
        print(f"{'Symbol':<12} {'Strategy':<20} {'Action':<6} {'Entry':>10} {'SL':>10} {'TP':>10} {'Days Ago':>8}")
        print("-" * 80)
        
        for s in all_signals:
            sig = s['signal']
            print(f"{s['symbol']:<12} {s['strategy']:<20} {sig['action']:<6} "
                  f"{sig['price']:>10.2f} {sig['sl']:>10.2f} {sig['tp']:>10.2f} {s['days_ago']:>8}")
        
        # Send Telegram Alerts for today's signals
        today_signals = [s for s in all_signals if s['days_ago'] == 0]
        
        if today_signals:
            print(f"\n🔔 Sending {len(today_signals)} Telegram alerts...")
            for s in today_signals:
                msg = format_signal_alert(s['symbol'], s['signal'], s['strategy'])
                send_telegram_alert(msg)
        
        # Save report
        df_report = pd.DataFrame(report_data)
        report_file = f"nifty50_scan_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
        df_report.to_csv(report_file, index=False)
        print(f"\n📁 Report saved: {report_file}")
        
    else:
        print("\n❌ No recent signals found")
    
    # Summary by strategy
    print("\n" + "=" * 60)
    print("  📊 SUMMARY BY STRATEGY")
    print("=" * 60)
    
    if report_data:
        df = pd.DataFrame(report_data)
        summary = df.groupby('strategy').agg({
            'symbol': 'count',
            'action': lambda x: (x == 'BUY').sum()
        }).rename(columns={'symbol': 'total_signals', 'action': 'buy_signals'})
        summary['sell_signals'] = summary['total_signals'] - summary['buy_signals']
        print(summary.to_string())
    
    print("\n" + "=" * 60)
    print(f"✅ Scan completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)


if __name__ == "__main__":
    main()
