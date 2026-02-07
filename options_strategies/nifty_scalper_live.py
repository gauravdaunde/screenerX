
import logging
import sys
import os
import time
import requests
from datetime import datetime

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from options_strategies.new_nifty_scanner import NiftyScalper

# Setup Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("NiftyScalperLive")

class NiftyScalperLive:
    """
    Live Scalper Orchestrator for NIFTY. 
    Manages up to 2 parallel trades with 2 lots each.
    Uses logic from new_nifty_scanner.py for entries.
    """
    def __init__(self):
        # Configuration
        self.symbol = "NIFTY-INDEX"
        self.scanner = NiftyScalper(symbol=self.symbol)
        
        # Risk Management
        self.max_parallel_trades = 2
        self.lots_per_trade = 2
        self.lot_size = 25  # Standard Nifty Lot Size as of 2024/25
        
        # Telegram Credentials
        self.telegram_token = os.getenv("TELEGRAM_BOT_TOKEN")
        self.chat_id = os.getenv("TELEGRAM_BOT_CHAT_ID") or os.getenv("TELEGRAM_CHAT_CHANNEL_ID")


        
        # State
        self.active_positions = [] # List of {type, entry, sl, tp, strat, timestamp}
        self.processed_timestamps = set()

    def send_telegram(self, message):
        """Sends a Telegram message if credentials are available."""
        if not self.telegram_token or not self.chat_id:
            logger.warning("Telegram Bot Token or Chat ID not found in environment.")
            return
            
        url = f"https://api.telegram.org/bot{self.telegram_token}/sendMessage"
        data = {"chat_id": self.chat_id, "text": message, "parse_mode": "Markdown"}
        try:
            requests.post(url, data=data, timeout=10)
        except Exception as e:
            logger.error(f"Failed to send Telegram alert: {e}")

    def manage_positions(self, current_price):
        """
        Monitors active positions for SL/TP hits.
        Args:
            current_price (float): Latest spot price of Nifty.
        """
        if not self.active_positions:
            return

        for pos in self.active_positions[:]:
            exit_reason = None
            pnl_pts = 0
            
            if pos['type'] == 'ENTER_LONG':
                if current_price <= pos['sl']:
                    exit_reason = "STOP LOSS HIT 🛑"
                    pnl_pts = pos['sl'] - pos['entry']
                elif current_price >= pos['tp']:
                    exit_reason = "TARGET HIT 🎯 (3.0R)"
                    pnl_pts = pos['tp'] - pos['entry']
            
            elif pos['type'] == 'ENTER_SHORT':
                if current_price >= pos['sl']:
                    exit_reason = "STOP LOSS HIT 🛑"
                    pnl_pts = pos['entry'] - pos['sl']
                elif current_price <= pos['tp']:
                    exit_reason = "TARGET HIT 🎯 (3.0R)"
                    pnl_pts = pos['entry'] - pos['tp']
            
            if exit_reason:
                total_pnl = pnl_pts * (self.lots_per_trade * self.lot_size)
                msg = (
                    f"🏁 *TRADE CLOSED*: {self.symbol}\n"
                    f"Reason: {exit_reason}\n"
                    f"Strategy: `{pos['strat']}`\n"
                    f"Exit Price: {current_price:.2f}\n"
                    f"Est. PnL: ₹{total_pnl:.2f} ({pnl_pts:.2f} pts)"
                )
                logger.info(f"Position Closed: {pos['strat']} | {exit_reason}")
                self.send_telegram(msg)
                self.active_positions.remove(pos)

    def run(self):
        """Main execution loop."""
        logger.info(f"🚀 NiftyScalperLive Started (Max Trades: {self.max_parallel_trades}, Lots: {self.lots_per_trade})")
        self.send_telegram(f"🤖 *Nifty Scalper Live Active*\nParallel Limits: {self.max_parallel_trades}\nLots: {self.lots_per_trade}\nStatus: Monitoring Market...")

        while True:
            try:
                # 1. Fetch latest data via scanner
                df = self.scanner.fetch_data()
                if df.empty:
                    logger.warning("Failed to fetch Nifty data. Retrying...")
                    time.sleep(30)
                    continue
                
                current_price = df.iloc[-1]['close']
                
                # 2. Manage Active Positions (Check SL/TP)
                self.manage_positions(current_price)
                
                # 3. Only scan for new entries if we have room
                if len(self.active_positions) < self.max_parallel_trades:
                    # Indirectly run scan by calling it on the scanner
                    # But since we already have data, we can optimize later, 
                    # but for now let's use the scanner.scan() for consistency
                    signal = self.scanner.scan()
                    
                    if signal.action != "WAIT" and signal.timestamp not in self.processed_timestamps:
                        # New Entry Found
                        self.processed_timestamps.add(signal.timestamp)
                        
                        # Add to active positions
                        new_pos = {
                            'type': signal.action,
                            'entry': signal.entry_price,
                            'sl': signal.stop_loss,
                            'tp': signal.target,
                            'strat': signal.strategy_name,
                            'ts': signal.timestamp
                        }
                        self.active_positions.append(new_pos)
                        
                        # Prepare Alert
                        emoji = "🚀" if "LONG" in signal.action else "🔻"
                        strat_emoji = "🎯" if "STRICT" in signal.strategy_name else "📈"
                        
                        msg = (
                            f"{emoji} *OPENING TRADE ({self.lots_per_trade} Lots)* - {self.symbol}\n"
                            f"{strat_emoji} Strategy: `{signal.strategy_name}`\n"
                            f"Time: {signal.timestamp}\n"
                            f"-------------------\n"
                            f"👉 *Entry Price*: {signal.entry_price:.2f}\n"
                            f"🛑 *Stop Loss*: {signal.stop_loss:.2f}\n"
                            f"🎯 *Target*: {signal.target:.2f}\n"
                            f"⭐ *Active Trades*: {len(self.active_positions)}/{self.max_parallel_trades}"
                        )
                        
                        logger.info(f"New Trade: {signal.strategy_name} {signal.action} @ {signal.entry_price}")
                        self.send_telegram(msg)
                
                else:
                    logger.info(f"Scan Paused: Max parallel trades ({self.max_parallel_trades}) reached. Monitoring...")

            except Exception as e:
                logger.error(f"Error in main loop: {e}")
                
            # Scan frequency: 60 seconds
            time.sleep(60)

if __name__ == "__main__":
    bot = NiftyScalperLive()
    bot.run()
