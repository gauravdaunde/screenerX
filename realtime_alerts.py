"""
Real-Time Alert System.

Continuously monitors for new signals and sends alerts via:
- Telegram
- Console notifications
- Log file

Can be run as a background service.
"""

import os
import time
import json
import requests
from datetime import datetime, timedelta
import pandas as pd
import yfinance as yf
from strategies.rsi_divergence import RSIDivergenceStrategy
from strategies.vwap_breakout import VWAPStrategy

# Configuration
SCAN_INTERVAL_MINUTES = 15  # How often to scan
ALERT_LOG_FILE = "alerts_log.json"

# Telegram Config
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# Watchlist (customize as needed)
WATCHLIST = [
    "RELIANCE", "TCS", "HDFCBANK", "ICICIBANK", "INFY",
    "SBIN", "BHARTIARTL", "KOTAKBANK", "LT", "AXISBANK",
    "MARUTI", "TATAMOTORS", "BAJFINANCE", "TITAN"
]

STRATEGIES = [
    RSIDivergenceStrategy(),
    VWAPStrategy()
]


class AlertManager:
    def __init__(self):
        self.sent_alerts = self._load_sent_alerts()
    
    def _load_sent_alerts(self):
        if os.path.exists(ALERT_LOG_FILE):
            try:
                with open(ALERT_LOG_FILE, 'r') as f:
                    return json.load(f)
            except:
                return {}
        return {}
    
    def _save_sent_alerts(self):
        with open(ALERT_LOG_FILE, 'w') as f:
            json.dump(self.sent_alerts, f, indent=2)
    
    def _get_alert_key(self, symbol, signal, strategy):
        """Generate unique key for signal to avoid duplicates."""
        sig_date = str(signal['time'])[:10]
        return f"{symbol}_{strategy}_{signal['action']}_{sig_date}"
    
    def is_duplicate(self, symbol, signal, strategy):
        """Check if we already sent this alert."""
        key = self._get_alert_key(symbol, signal, strategy)
        return key in self.sent_alerts
    
    def mark_sent(self, symbol, signal, strategy):
        """Mark alert as sent."""
        key = self._get_alert_key(symbol, signal, strategy)
        self.sent_alerts[key] = {
            'time': datetime.now().isoformat(),
            'signal': {
                'action': signal['action'],
                'price': signal['price'],
                'sl': signal['sl'],
                'tp': signal['tp']
            }
        }
        self._save_sent_alerts()
    
    def send_telegram(self, message):
        """Send Telegram notification."""
        if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
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
        except:
            return False
    
    def send_alert(self, symbol, signal, strategy_name):
        """Send alert through all channels."""
        if self.is_duplicate(symbol, signal, strategy_name):
            return False
        
        action = signal['action']
        emoji = "🟢" if action == "BUY" else "🔴"
        
        # Calculate RR
        if action == "BUY":
            risk = signal['price'] - signal['sl']
            reward = signal['tp'] - signal['price']
        else:
            risk = signal['sl'] - signal['price']
            reward = signal['price'] - signal['tp']
        
        rr = reward / risk if risk > 0 else 0
        
        message = f"""
{emoji} <b>NEW {action} SIGNAL</b>

📈 Symbol: <b>{symbol}</b>
📊 Strategy: {strategy_name}

💰 Entry: ₹{signal['price']:.2f}
🛑 Stop Loss: ₹{signal['sl']:.2f}
🎯 Target: ₹{signal['tp']:.2f}

⚖️ Risk:Reward = 1:{rr:.1f}
📝 {signal.get('reason', '')}

⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        
        # Console
        print("\n" + "=" * 50)
        print(f"🔔 ALERT: {action} {symbol}")
        print(f"   Entry: ₹{signal['price']:.2f} | SL: ₹{signal['sl']:.2f} | TP: ₹{signal['tp']:.2f}")
        print(f"   Strategy: {strategy_name}")
        print("=" * 50)
        
        # Telegram
        self.send_telegram(message)
        
        # Mark as sent
        self.mark_sent(symbol, signal, strategy_name)
        
        return True


def scan_for_signals(symbols, strategies, alert_manager):
    """Scan symbols and send alerts for new signals."""
    new_signals = 0
    
    for symbol in symbols:
        try:
            ticker = f"{symbol}.NS"
            data = yf.download(ticker, period="3mo", interval="1d", progress=False)
            
            if isinstance(data.columns, pd.MultiIndex):
                data.columns = data.columns.get_level_values(0)
            
            if data.empty or len(data) < 50:
                continue
            
            df = data.copy()
            df.columns = [c.lower() for c in df.columns]
            
            for strat in strategies:
                try:
                    signals = strat.check_signals(df)
                    
                    # Only check latest signal (today or yesterday)
                    for sig in signals:
                        sig_date = pd.Timestamp(sig['time']).date()
                        today = datetime.now().date()
                        
                        if (today - sig_date).days <= 1:
                            if alert_manager.send_alert(symbol, sig, strat.name()):
                                new_signals += 1
                
                except Exception as e:
                    pass
        
        except Exception as e:
            pass
    
    return new_signals


def run_realtime_scanner():
    """Run continuous real-time scanner."""
    print("=" * 60)
    print("  🔔 REAL-TIME SIGNAL ALERT SYSTEM")
    print("=" * 60)
    print(f"📊 Watching {len(WATCHLIST)} symbols")
    print(f"⏱️  Scan interval: {SCAN_INTERVAL_MINUTES} minutes")
    print(f"🔔 Telegram: {'Configured' if TELEGRAM_BOT_TOKEN else 'Not configured'}")
    print()
    
    alert_manager = AlertManager()
    
    # Initial message
    if TELEGRAM_BOT_TOKEN:
        alert_manager.send_telegram(
            f"🚀 <b>Scanner Started</b>\n\n"
            f"Watching {len(WATCHLIST)} symbols\n"
            f"Strategies: RSI Divergence v2, VWAP Breakout\n"
            f"Scan interval: {SCAN_INTERVAL_MINUTES} min"
        )
    
    scan_count = 0
    
    while True:
        scan_count += 1
        current_time = datetime.now().strftime('%H:%M:%S')
        
        print(f"\n[{current_time}] Scan #{scan_count} starting...")
        
        new_signals = scan_for_signals(WATCHLIST, STRATEGIES, alert_manager)
        
        if new_signals > 0:
            print(f"[{current_time}] ✅ Found {new_signals} new signal(s)")
        else:
            print(f"[{current_time}] No new signals")
        
        print(f"[{current_time}] Next scan in {SCAN_INTERVAL_MINUTES} minutes...")
        
        time.sleep(SCAN_INTERVAL_MINUTES * 60)


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--once":
        # Single scan mode
        print("Running single scan...")
        alert_manager = AlertManager()
        new_signals = scan_for_signals(WATCHLIST, STRATEGIES, alert_manager)
        print(f"Found {new_signals} new signals")
    else:
        # Continuous mode
        run_realtime_scanner()
