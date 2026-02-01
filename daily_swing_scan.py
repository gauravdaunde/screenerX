#!/usr/bin/env python3
"""
🚀 DAILY SWING TRADING SCANNER
Runs multiple strategies on Nifty 50 and sends a consolidated Telegram report.

Strategies:
1. SuperTrend + Pivot Breakout (Trend Following)
2. Bollinger Band Mean Reversion (Dip Buying)
"""

import os
import sys
import pandas as pd
# import pandas_ta as ta  # Fallback to manual if missing
import requests
from datetime import datetime
from dotenv import load_dotenv

# Import strategies and data
from swing_strategies import NIFTY50, fetch_stock_data
from swing_strategies.supertrend_pivot import scan_stock as scan_supertrend

# Load environment variables
load_dotenv()
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")


def calculate_bb_signal(symbol: str, df: pd.DataFrame):
    """
    Check for BB Mean Reversion Signal.
    """
    # Manual BB Calculation (No dependency)
    df['ma20'] = df['close'].rolling(20).mean()
    df['std20'] = df['close'].rolling(20).std()
    df['upper'] = df['ma20'] + (2 * df['std20'])
    df['lower'] = df['ma20'] - (2 * df['std20'])
    
    # Trend Filter (200 SMA)
    df['sma200'] = df['close'].rolling(200).mean()
    
    current_price = df['close'].iloc[-1]
    lower_band = df['lower'].iloc[-1]
    upper_band = df['upper'].iloc[-1]
    sma200 = df['sma200'].iloc[-1]
    
    # 1. Dip Buy (Oversold in Uptrend is best, but pure reversion works too)
    if current_price <= lower_band * 1.015:  # Within 1.5% of lower band
        confidence = 0.6
        reasons = ["Price near Lower BB"]
        
        # Boost confidence if in uptrend
        if not pd.isna(sma200) and current_price > sma200:
            confidence += 0.2
            reasons.append("Major Uptrend Support")
            
        return {
            "symbol": symbol,
            "strategy": "BB Mean Reversion",
            "signal": "BUY",
            "price": current_price,
            "stop_loss": current_price * 0.97,  # 3% SL
            "target": df['ma20'].iloc[-1],      # Target Mid Band
            "confidence": confidence,
            "reason": ", ".join(reasons)
        }
        
    return None


def send_telegram_report(signals):
    """Send consolidated report to Telegram."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("❌ Telegram credentials missing")
        return

    if not signals:
        message = f"<b>📉 Daily Swing Scan ({datetime.now().strftime('%d-%b')})</b>\n\nNo high-confidence setups found today."
    else:
        message = f"<b>🚀 DAILY SWING SIGNALS ({datetime.now().strftime('%d-%b')})</b>\n\n"
        
        # Group by strategy
        strategies = {}
        for s in signals:
            strat = s['strategy']
            if strat not in strategies:
                strategies[strat] = []
            strategies[strat].append(s)
            
        for strat, items in strategies.items():
            message += f"<b>📌 {strat}</b>\n"
            for s in items:
                emoji = "🟢" if s['signal'] == "BUY" else "🔴"
                conf_icon = "🔥" if s['confidence'] >= 0.8 else "✨"
                
                message += f"{emoji} <b>{s['symbol']}</b> @ ₹{s['price']:,.0f}\n"
                message += f"   SL: ₹{s['stop_loss']:,.0f} | TGT: ₹{s['target']:,.0f}\n"
                message += f"   Reason: {s['reason']} ({int(s['confidence']*100)}% {conf_icon})\n\n"
            message += "----------------------------\n"
            
        message += "⚠️ <i>Algo-generated. DYOR.</i>"

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "HTML"}
    
    try:
        requests.post(url, json=payload)
        print("✅ Telegram report sent!")
    except Exception as e:
        print(f"❌ Failed to send Telegram: {e}")


def get_swing_signals(symbols):
    """
    Run swing strategies on a list of symbols.
    Returns list of signal dictionaries.
    """
    all_signals = []
    total = len(symbols)
    
    for idx, symbol in enumerate(symbols):
        print(f"\r[{idx+1}/{total}] Scanning {symbol:<15}", end="", flush=True)
        
        try:
            # Fetch 1y data to ensure SMA200 can be calculated
            df = fetch_stock_data(symbol, period="1y")
            if df.empty or len(df) < 50:
                continue

            # --- STRATEGY 1: SuperTrend Pivot --- 
            st_signal = scan_supertrend(symbol, df)
            if st_signal and st_signal['signal'] in ['BUY', 'SELL']:
                # Normalize format
                if st_signal['confidence'] >= 0.5: # Min threshold
                    all_signals.append({
                        "symbol": symbol,
                        "strategy": "SuperTrend Pivot",
                        "signal": st_signal['signal'],
                        "price": st_signal['entry_price'],
                        "stop_loss": st_signal['stop_loss'],
                        "target": st_signal['target'],
                        "confidence": st_signal['confidence'],
                        "reason": st_signal['reason']
                    })

            # --- STRATEGY 2: BB Mean Reversion ---
            bb_signal = calculate_bb_signal(symbol, df)
            if bb_signal:
                all_signals.append(bb_signal)
                
        except Exception as e:
            continue
            
    # Sort by confidence
    all_signals.sort(key=lambda x: x['confidence'], reverse=True)
    return all_signals


def main():
    print("=" * 60)
    print(f"🚀 RUNNING DAILY SWING SCAN ({datetime.now().strftime('%Y-%m-%d')})")
    print("=" * 60)
    
    signals = get_swing_signals(NIFTY50)
    print("\n\n✅ Scan Complete.")
    
    # Print to console
    if signals:
        print(f"\nFound {len(signals)} signals:")
        for s in signals:
            print(f"  • {s['symbol']} ({s['strategy']}): {s['signal']} (Conf: {s['confidence']:.2f})")
    else:
        print("\nNo signals found.")
        
    # Send to Telegram
    send_telegram_report(signals)


if __name__ == "__main__":
    main()
