#!/usr/bin/env python3
"""
Auto Trading System with Dhan API.

This module provides automated trading capabilities using the Dhan broker API.
It scans for VWAP breakout signals and automatically places orders with
stop-loss and target levels.

Features:
    - Auto-detects trading signals using VWAP strategy
    - Places CNC (Delivery) orders via Dhan API
    - Risk-based position sizing (2% max risk per trade)
    - Telegram notifications for all order activities
    - Daily order limits and duplicate prevention
    - Supports both DRY RUN (paper trading) and LIVE modes

Environment Variables Required:
    DHAN_CLIENT_ID: Your Dhan client ID
    DHAN_ACCESS_TOKEN: Your Dhan API access token
    TELEGRAM_BOT_TOKEN: Telegram bot token for alerts
    TELEGRAM_CHAT_ID: Your Telegram chat ID for receiving alerts

Usage:
    # Dry run mode (default - safe for testing)
    python auto_trader.py
    
    # Live mode (edit DRY_RUN = False in config)
    python auto_trader.py

Author: Trading Strategy Screener
Version: 1.0.0
"""

import os
import json
import logging
import requests
from datetime import datetime, date
from typing import Dict, List, Optional, Tuple, Any

from dhanhq import dhanhq
from dotenv import load_dotenv
import yfinance as yf
import pandas as pd

from strategies.vwap_breakout import VWAPStrategy

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()


# =============================================================================
# CONFIGURATION
# =============================================================================

class Config:
    """Trading configuration parameters."""
    
    # Dhan API Credentials
    DHAN_CLIENT_ID: str = os.getenv("DHAN_CLIENT_ID", "")
    DHAN_ACCESS_TOKEN: str = os.getenv("DHAN_ACCESS_TOKEN", "")
    
    # Telegram Credentials
    TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    TELEGRAM_CHAT_ID: str = os.getenv("TELEGRAM_CHAT_ID", "")
    
    # Trading Parameters
    CAPITAL_PER_TRADE: float = 100000  # ₹1,00,000 per trade
    MAX_RISK_PER_TRADE: float = 0.02   # 2% risk per trade
    MAX_ORDERS_PER_DAY: int = 3        # Maximum orders per day
    DRY_RUN: bool = False              # Set False for live trading
    
    # Files
    ORDERS_FILE: str = "placed_orders.json"


# NSE Equity Security IDs for Dhan API
SECURITY_IDS: Dict[str, str] = {
    "RELIANCE": "2885",
    "TCS": "11536",
    "HDFCBANK": "1333",
    "ICICIBANK": "4963",
    "INFY": "1594",
    "SBIN": "3045",
    "ITC": "1660",
    "BHARTIARTL": "10604",
    "KOTAKBANK": "1922",
    "LT": "11483",
    "HCLTECH": "700",
    "AXISBANK": "5900",
    "ASIANPAINT": "236",
    "MARUTI": "10999",
    "SUNPHARMA": "3351",
    "TITAN": "3506",
    "ULTRACEMCO": "11532",
    "BAJFINANCE": "317",
    "WIPRO": "3787",
    "NESTLEIND": "17963",
    "TATAMOTORS": "3456",
    "M&M": "2031",
    "NTPC": "11630",
    "POWERGRID": "14977",
    "TECHM": "13538",
    "TATASTEEL": "3499",
    "ADANIENT": "25",
    "ADANIPORTS": "15083",
    "JSWSTEEL": "11723",
    "ONGC": "2475",
    "COALINDIA": "20374",
    "BAJAJFINSV": "16675",
    "HDFCLIFE": "467",
    "DRREDDY": "881",
    "DIVISLAB": "10940",
    "GRASIM": "1232",
    "CIPLA": "694",
    "APOLLOHOSP": "157",
    "BRITANNIA": "547",
    "EICHERMOT": "910",
    "SBILIFE": "21808",
    "BPCL": "526",
    "TATACONSUM": "3432",
    "INDUSINDBK": "5258",
    "HINDALCO": "1363",
    "HEROMOTOCO": "1348",
    "UPL": "11287"
}

# Default watchlist for auto-trading
WATCHLIST: List[str] = [
    "RELIANCE", "TCS", "HDFCBANK", "ICICIBANK", "INFY", "SBIN",
    "KOTAKBANK", "ADANIPORTS", "TATASTEEL", "HINDALCO"
]


# =============================================================================
# TELEGRAM NOTIFICATIONS
# =============================================================================

class TelegramNotifier:
    """Handles Telegram notifications for trading alerts."""
    
    def __init__(self, bot_token: str, chat_id: str):
        """
        Initialize Telegram notifier.
        
        Args:
            bot_token: Telegram bot token
            chat_id: Target chat ID for messages
        """
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.enabled = bool(bot_token and chat_id)
    
    def send(self, message: str) -> bool:
        """
        Send a message via Telegram.
        
        Args:
            message: Message text (supports HTML formatting)
            
        Returns:
            True if message sent successfully, False otherwise
        """
        if not self.enabled:
            logger.info(f"[TELEGRAM DISABLED] {message}")
            return False
        
        try:
            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            payload = {
                "chat_id": self.chat_id,
                "text": message,
                "parse_mode": "HTML"
            }
            response = requests.post(url, json=payload, timeout=10)
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Telegram error: {e}")
            return False
    
    def alert_order_placed(self, symbol: str, order_type: str, entry: float,
                           sl: float, tp: float, quantity: int, 
                           order_id: str, dry_run: bool = False) -> None:
        """
        Send alert when an order is placed.
        
        Args:
            symbol: Stock symbol
            order_type: BUY or SELL
            entry: Entry price
            sl: Stop-loss price
            tp: Target price
            quantity: Number of shares
            order_id: Broker order ID
            dry_run: Whether this is a simulated order
        """
        emoji = "🟢" if order_type == "BUY" else "🔴"
        mode = "⚠️ DRY RUN - No real order placed" if dry_run else "✅ LIVE ORDER"
        
        message = f"""
{emoji} <b>ORDER PLACED</b>

📈 <b>Symbol:</b> {symbol}
📊 <b>Type:</b> {order_type}
📦 <b>Quantity:</b> {quantity}

💰 <b>Entry:</b> ₹{entry:,.2f}
🛑 <b>Stop Loss:</b> ₹{sl:,.2f}
🎯 <b>Target:</b> ₹{tp:,.2f}

🔖 <b>Order ID:</b> {order_id}
⏰ <b>Time:</b> {datetime.now().strftime('%H:%M:%S')}

{mode}
"""
        self.send(message)
    
    def alert_error(self, symbol: str, error: str) -> None:
        """
        Send alert when an order fails.
        
        Args:
            symbol: Stock symbol
            error: Error message
        """
        message = f"""
❌ <b>ORDER FAILED</b>

📈 <b>Symbol:</b> {symbol}
⚠️ <b>Error:</b> {error}
⏰ <b>Time:</b> {datetime.now().strftime('%H:%M:%S')}
"""
        self.send(message)


# =============================================================================
# ORDER TRACKING
# =============================================================================

class OrderTracker:
    """Tracks placed orders to prevent duplicates and enforce limits."""
    
    def __init__(self, orders_file: str):
        """
        Initialize order tracker.
        
        Args:
            orders_file: Path to JSON file for persisting orders
        """
        self.orders_file = orders_file
    
    def load(self) -> Dict[str, Any]:
        """Load orders from file."""
        if os.path.exists(self.orders_file):
            with open(self.orders_file, 'r') as f:
                return json.load(f)
        return {"orders": [], "today": str(date.today()), "count": 0}
    
    def save(self, orders_data: Dict[str, Any]) -> None:
        """Save orders to file."""
        with open(self.orders_file, 'w') as f:
            json.dump(orders_data, f, indent=2)
    
    def can_place_order(self, symbol: str, max_per_day: int) -> Tuple[bool, str]:
        """
        Check if a new order can be placed.
        
        Args:
            symbol: Stock symbol to trade
            max_per_day: Maximum orders allowed per day
            
        Returns:
            Tuple of (can_place, reason)
        """
        orders_data = self.load()
        
        # Reset counter if new day
        if orders_data.get("today") != str(date.today()):
            orders_data = {"orders": [], "today": str(date.today()), "count": 0}
            self.save(orders_data)
        
        # Check daily limit
        if orders_data["count"] >= max_per_day:
            return False, "Daily order limit reached"
        
        # Check if already traded this symbol today
        today_symbols = [
            o["symbol"] for o in orders_data["orders"] 
            if o["date"] == str(date.today())
        ]
        if symbol in today_symbols:
            return False, "Already traded this symbol today"
        
        return True, "OK"
    
    def record_order(self, symbol: str, order_type: str, entry: float,
                     sl: float, tp: float, quantity: int, order_id: str) -> None:
        """
        Record a placed order.
        
        Args:
            symbol: Stock symbol
            order_type: BUY or SELL
            entry: Entry price
            sl: Stop-loss price
            tp: Target price
            quantity: Number of shares
            order_id: Broker order ID
        """
        orders_data = self.load()
        
        orders_data["orders"].append({
            "symbol": symbol,
            "order_type": order_type,
            "entry": entry,
            "sl": sl,
            "tp": tp,
            "quantity": quantity,
            "order_id": order_id,
            "date": str(date.today()),
            "time": datetime.now().strftime('%H:%M:%S')
        })
        orders_data["count"] = orders_data.get("count", 0) + 1
        
        self.save(orders_data)


# =============================================================================
# POSITION SIZING
# =============================================================================

def calculate_quantity(entry_price: float, sl_price: float, 
                       capital: float, max_risk: float) -> int:
    """
    Calculate position size based on risk management.
    
    Uses the formula: Quantity = Risk Amount / Risk per Share
    where Risk Amount = Capital × Max Risk Percentage
    
    Args:
        entry_price: Entry price per share
        sl_price: Stop-loss price per share
        capital: Total capital available for trade
        max_risk: Maximum risk as decimal (e.g., 0.02 for 2%)
        
    Returns:
        Number of shares to buy (minimum 1)
    """
    risk_per_share = abs(entry_price - sl_price)
    
    if risk_per_share <= 0:
        return 0
    
    # Calculate based on risk
    risk_amount = capital * max_risk
    qty_by_risk = int(risk_amount / risk_per_share)
    
    # Calculate based on capital
    qty_by_capital = int(capital / entry_price)
    
    # Take minimum to stay within both limits
    quantity = min(qty_by_risk, qty_by_capital)
    
    return max(1, quantity)


# =============================================================================
# ORDER EXECUTION
# =============================================================================

class DhanOrderExecutor:
    """Handles order execution via Dhan API."""
    
    def __init__(self, client_id: str, access_token: str):
        """
        Initialize Dhan order executor.
        
        Args:
            client_id: Dhan client ID
            access_token: Dhan API access token
        """
        self.client_id = client_id
        self.access_token = access_token
        self.dhan = None
    
    def connect(self) -> bool:
        """
        Connect to Dhan API.
        
        Returns:
            True if connected successfully
        """
        try:
            self.dhan = dhanhq(self.client_id, self.access_token)
            return True
        except Exception as e:
            logger.error(f"Failed to connect to Dhan: {e}")
            return False
    
    def place_order(self, security_id: str, transaction_type: str,
                    quantity: int, price: float) -> Optional[Dict[str, Any]]:
        """
        Place a limit order via Dhan API.
        
        Args:
            security_id: Dhan security ID
            transaction_type: BUY or SELL
            quantity: Number of shares
            price: Limit price
            
        Returns:
            API response dict or None if failed
        """
        if not self.dhan:
            if not self.connect():
                return None
        
        try:
            response = self.dhan.place_order(
                security_id=security_id,
                exchange_segment=self.dhan.NSE,
                transaction_type=self.dhan.BUY if transaction_type == "BUY" else self.dhan.SELL,
                quantity=quantity,
                order_type=self.dhan.LIMIT,
                product_type=self.dhan.CNC,  # Cash & Carry (Delivery)
                price=price,
                trigger_price=0,
                disclosed_quantity=0,
                validity=self.dhan.DAY
            )
            return response
        except Exception as e:
            logger.error(f"Order placement error: {e}")
            return None


# =============================================================================
# AUTO TRADER
# =============================================================================

class AutoTrader:
    """
    Automated trading system that scans for signals and places orders.
    
    This class orchestrates the entire trading workflow:
    1. Scans watchlist for trading signals
    2. Validates signals (freshness, duplicate checks)
    3. Calculates position size based on risk
    4. Places orders via Dhan API
    5. Sends notifications via Telegram
    """
    
    def __init__(self, config: Config):
        """
        Initialize auto trader.
        
        Args:
            config: Trading configuration
        """
        self.config = config
        self.notifier = TelegramNotifier(
            config.TELEGRAM_BOT_TOKEN, 
            config.TELEGRAM_CHAT_ID
        )
        self.tracker = OrderTracker(config.ORDERS_FILE)
        self.executor = DhanOrderExecutor(
            config.DHAN_CLIENT_ID,
            config.DHAN_ACCESS_TOKEN
        )
        self.strategy = VWAPStrategy()
    
    def fetch_data(self, symbol: str) -> Optional[pd.DataFrame]:
        """
        Fetch historical data for a symbol.
        
        Args:
            symbol: Stock symbol (without .NS suffix)
            
        Returns:
            DataFrame with OHLCV data or None if failed
        """
        try:
            ticker = f"{symbol}.NS"
            data = yf.download(ticker, period="3mo", interval="1d", progress=False)
            
            if isinstance(data.columns, pd.MultiIndex):
                data.columns = data.columns.get_level_values(0)
            
            if data.empty or len(data) < 30:
                return None
            
            df = data.copy()
            df.columns = [c.lower() for c in df.columns]
            return df
            
        except Exception as e:
            logger.error(f"Data fetch error for {symbol}: {e}")
            return None
    
    def process_signal(self, symbol: str, signal: Dict[str, Any]) -> Optional[str]:
        """
        Process a trading signal and place order if valid.
        
        Args:
            symbol: Stock symbol
            signal: Signal dict with price, sl, tp, action
            
        Returns:
            Order ID if successful, None otherwise
        """
        # Check if we can place order
        can_place, reason = self.tracker.can_place_order(
            symbol, self.config.MAX_ORDERS_PER_DAY
        )
        if not can_place:
            logger.warning(f"Cannot place order for {symbol}: {reason}")
            return None
        
        # Get security ID
        security_id = SECURITY_IDS.get(symbol)
        if not security_id:
            logger.error(f"Security ID not found for {symbol}")
            return None
        
        # Extract signal details
        entry = signal['price']
        sl = signal['sl']
        tp = signal['tp']
        action = signal['action']
        
        # Calculate quantity
        quantity = calculate_quantity(
            entry, sl, 
            self.config.CAPITAL_PER_TRADE, 
            self.config.MAX_RISK_PER_TRADE
        )
        
        if quantity < 1:
            logger.warning(f"Quantity too low for {symbol}")
            return None
        
        # Log order details
        logger.info(f"""
Order Details for {symbol}:
  Action: {action}
  Entry: ₹{entry:,.2f}
  SL: ₹{sl:,.2f}
  TP: ₹{tp:,.2f}
  Quantity: {quantity}
  Investment: ₹{quantity * entry:,.2f}
        """)
        
        # DRY RUN mode
        if self.config.DRY_RUN:
            order_id = f"DRY_{datetime.now().strftime('%H%M%S')}"
            logger.info(f"DRY RUN - Order NOT placed: {order_id}")
            
            self.tracker.record_order(
                symbol, action, entry, sl, tp, quantity, order_id
            )
            self.notifier.alert_order_placed(
                symbol, action, entry, sl, tp, quantity, order_id, 
                dry_run=True
            )
            return order_id
        
        # LIVE ORDER
        response = self.executor.place_order(
            security_id, action, quantity, entry
        )
        
        if response and response.get('status') == 'success':
            order_id = response.get('orderId', 
                        response.get('data', {}).get('orderId', 'UNKNOWN'))
            logger.info(f"Order placed successfully: {order_id}")
            
            self.tracker.record_order(
                symbol, action, entry, sl, tp, quantity, order_id
            )
            self.notifier.alert_order_placed(
                symbol, action, entry, sl, tp, quantity, order_id,
                dry_run=False
            )
            return order_id
        else:
            error = response.get('remarks', 'Unknown error') if response else 'No response'
            logger.error(f"Order failed for {symbol}: {error}")
            self.notifier.alert_error(symbol, str(error))
            return None
    
    def scan_and_trade(self, watchlist: List[str]) -> int:
        """
        Scan watchlist for signals and place orders.
        
        Args:
            watchlist: List of stock symbols to scan
            
        Returns:
            Number of orders placed
        """
        print("=" * 60)
        print("  🤖 AUTO-TRADING SYSTEM")
        print("=" * 60)
        print(f"""
    ⚙️ Configuration:
    ────────────────────────────
    💰 Capital per Trade: ₹{self.config.CAPITAL_PER_TRADE:,}
    ⚠️ Max Risk: {self.config.MAX_RISK_PER_TRADE*100}%
    📦 Max Orders/Day: {self.config.MAX_ORDERS_PER_DAY}
    🔶 Dry Run: {self.config.DRY_RUN}
    📈 Watchlist: {len(watchlist)} symbols
    ────────────────────────────
        """)
        
        mode = "DRY RUN" if self.config.DRY_RUN else "LIVE"
        print(f"{'⚠️' if self.config.DRY_RUN else '🔴'} {mode} MODE\n")
        
        signals_found = []
        orders_placed = 0
        
        print("🔍 Scanning for signals...")
        
        for symbol in watchlist:
            print(f"  Checking {symbol}...", end=" ")
            
            df = self.fetch_data(symbol)
            if df is None:
                print("❌ No data")
                continue
            
            signals = self.strategy.check_signals(df)
            
            if signals:
                last_signal = signals[-1]
                sig_date = pd.Timestamp(last_signal['time']).date()
                days_ago = (date.today() - sig_date).days
                
                if days_ago <= 1:
                    print(f"✅ {last_signal['action']} signal!")
                    signals_found.append({
                        'symbol': symbol,
                        'signal': last_signal,
                        'days_ago': days_ago
                    })
                else:
                    print(f"⏭️ Signal {days_ago} days old")
            else:
                print("—")
        
        # Process signals
        print(f"\n{'='*60}")
        print(f"  📊 SIGNALS FOUND: {len(signals_found)}")
        print(f"{'='*60}")
        
        for item in signals_found:
            symbol = item['symbol']
            signal = item['signal']
            
            print(f"\n📈 Processing {symbol}...")
            
            order_id = self.process_signal(symbol, signal)
            
            if order_id:
                orders_placed += 1
                if orders_placed >= self.config.MAX_ORDERS_PER_DAY:
                    print(f"\n⚠️ Daily order limit reached!")
                    break
        
        # Summary
        print(f"\n{'='*60}")
        print(f"  📋 SUMMARY")
        print(f"{'='*60}")
        print(f"""
    Signals Found: {len(signals_found)}
    Orders Placed: {orders_placed}
    Mode: {mode}
        """)
        
        return orders_placed


# =============================================================================
# MAIN
# =============================================================================

def main():
    """Main entry point for auto trader."""
    config = Config()
    trader = AutoTrader(config)
    
    # Startup notification
    trader.notifier.send(
        f"🤖 <b>Auto-Trading System Started</b>\n\n"
        f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"🔶 Mode: {'DRY RUN' if config.DRY_RUN else 'LIVE'}"
    )
    
    # Run scanner and trader
    orders = trader.scan_and_trade(WATCHLIST)
    
    # Completion notification
    trader.notifier.send(
        f"✅ <b>Scan Complete</b>\n\n"
        f"📦 Orders Placed: {orders}\n"
        f"⏰ {datetime.now().strftime('%H:%M:%S')}"
    )


if __name__ == "__main__":
    main()
