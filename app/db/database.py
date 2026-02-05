
import sqlite3
from datetime import datetime
from app.core.config import DB_NAME, logger

def get_connection():
    """Helper to get connection with proper timeout and WAL mode."""
    conn = sqlite3.connect(DB_NAME, timeout=10)
    conn.execute("PRAGMA journal_mode=WAL;") 
    return conn

def init_db():
    """Initialize the database tables."""
    try:
        with get_connection() as conn:
            c = conn.cursor()
            
            # Create Trades Table
            c.execute('''
                CREATE TABLE IF NOT EXISTS trades (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    strategy TEXT,
                    signal_type TEXT, -- BUY / SELL
                    entry_price REAL,
                    quantity INTEGER,
                    entry_time TIMESTAMP,
                    sl REAL,
                    tp REAL,
                    status TEXT, -- OPEN, CLOSED
                    exit_price REAL,
                    exit_time TIMESTAMP,
                    pnl REAL,
                    exit_reason TEXT,
                    asset_type TEXT DEFAULT 'STOCK' -- STOCK, OPTION
                )
            ''')
            
            # Migration: Add asset_type if missing (for existing DBs)
            try:
                c.execute("ALTER TABLE trades ADD COLUMN asset_type TEXT DEFAULT 'STOCK'")
            except sqlite3.OperationalError:
                pass # Column already exists
            
            # Create Strategy Wallets Table (New)
            c.execute('''
                CREATE TABLE IF NOT EXISTS strategy_wallets (
                    strategy TEXT PRIMARY KEY,
                    allocation REAL, -- Total Capital Allocated
                    available_balance REAL, -- Cash currently available for trading
                    updated_at TIMESTAMP
                )
            ''')
            
            conn.commit()
        logger.info("✅ Database initialized (WAL Mode Enabled).")
    except Exception as e:
        logger.error(f"❌ Database initialization failed: {e}")

def ensure_wallet_exists(strategy: str):
    """Ensure a wallet exists for the strategy. Default 100k if not."""
    with get_connection() as conn:
        c = conn.cursor()
        c.execute('SELECT count(*) FROM strategy_wallets WHERE strategy = ?', (strategy,))
        if c.fetchone()[0] == 0:
            default_capital = 100000.0
            c.execute('''
                INSERT INTO strategy_wallets (strategy, allocation, available_balance, updated_at)
                VALUES (?, ?, ?, ?)
            ''', (strategy, default_capital, default_capital, datetime.now()))
            conn.commit()
            logger.info(f"💼 Created new wallet for '{strategy}' with ₹{default_capital:,.2f}")

def get_strategy_balance(strategy: str) -> float:
    ensure_wallet_exists(strategy)
    with get_connection() as conn:
        c = conn.cursor()
        c.execute('SELECT available_balance FROM strategy_wallets WHERE strategy = ?', (strategy,))
        bal = c.fetchone()[0]
    return bal

def get_balance() -> float:
    """Get total available balance across all strategy wallets."""
    with get_connection() as conn:
        c = conn.cursor()
        c.execute('SELECT COALESCE(SUM(available_balance), 0) FROM strategy_wallets')
        total = c.fetchone()[0]
    return total

def update_strategy_balance(strategy: str, amount_change: float):
    ensure_wallet_exists(strategy)
    with get_connection() as conn:
        c = conn.cursor()
        
        # Get current
        c.execute('SELECT available_balance FROM strategy_wallets WHERE strategy = ?', (strategy,))
        result = c.fetchone()
        if not result:
            logger.error(f"Cannot update balance: Strategy '{strategy}' not found.")
            return

        current = result[0]
        new_bal = current + amount_change
        
        c.execute('UPDATE strategy_wallets SET available_balance = ?, updated_at = ? WHERE strategy = ?', (new_bal, datetime.now(), strategy))
        conn.commit()

def log_trade(symbol: str, strategy: str, signal_type: str, price: float, qty: int, sl: float, tp: float, asset_type: str = "STOCK"):
    with get_connection() as conn:
        c = conn.cursor()
        
        c.execute('''
            INSERT INTO trades (symbol, strategy, signal_type, entry_price, quantity, entry_time, sl, tp, status, asset_type)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (symbol, strategy, signal_type, price, qty, datetime.now(), sl, tp, 'OPEN', asset_type))
        
        conn.commit()
    
    # Deduct invested amount from STRATEGY balance
    invested_amount = price * qty
    update_strategy_balance(strategy, -invested_amount)
    
    logger.info(f"📝 Trade Logged: {signal_type} {qty} {symbol} ({strategy}) @ {price} (Invested: ₹{invested_amount:,.2f}) [Type: {asset_type}]")

def close_trade_in_db(trade_id: int, exit_price: float, reason: str) -> float:
    with get_connection() as conn:
        c = conn.cursor()
        
        # Get trade details
        c.execute('SELECT entry_price, quantity, signal_type, symbol, strategy FROM trades WHERE id = ?', (trade_id,))
        row = c.fetchone()
        
        if not row:
            logger.error(f"❌ Trade ID {trade_id} not found.")
            return 0.0
            
        entry_price, qty, signal, symbol, strategy = row
        
        # Calculate PnL
        if signal == 'BUY':
            pnl = (exit_price - entry_price) * qty
        else: # SELL/SHORT
            pnl = (entry_price - exit_price) * qty
            
        c.execute('''
            UPDATE trades 
            SET status = 'CLOSED', exit_price = ?, exit_time = ?, pnl = ?, exit_reason = ?
            WHERE id = ?
        ''', (exit_price, datetime.now(), pnl, reason, trade_id))
        
        conn.commit()
    
    # Add back the exit value to STRATEGY balance
    exit_value = exit_price * qty
    update_strategy_balance(strategy, exit_value)
    
    logger.info(f"💰 Trade Closed: {symbol} | Exit Value: ₹{exit_value:,.2f} | PnL: ₹{pnl:+,.2f} | Wallet: {strategy}")
    return pnl

if __name__ == "__main__":
    init_db()
